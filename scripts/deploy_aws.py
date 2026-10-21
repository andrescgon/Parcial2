#!/usr/bin/env python3
"""
Master deployment script for AWS Learner Lab.
Creates S3 bucket, uploads data, launches EMR, creates RDS, EC2, Athena tables.
"""
import boto3
import json
import time
import sys
import os

# ── AWS Session ──
session = boto3.Session(region_name="us-east-1")
BUCKET = "airline-analytics-kevin-874"
ACCOUNT = "458849247707"

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

# ═══════════════════════════════════════════════════════════════
# STEP 1: Create S3 Bucket
# ═══════════════════════════════════════════════════════════════
def create_bucket():
    global BUCKET
    s3 = session.client("s3")
    try:
        s3.create_bucket(Bucket=BUCKET)
        log(f"✅ S3 bucket '{BUCKET}' created")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        log(f"✅ S3 bucket '{BUCKET}' already exists (owned by us)")
    except Exception as e:
        if "BucketAlreadyExists" in str(e):
            log(f"⚠️  Bucket name taken globally, trying alternative...")
            BUCKET = f"airline-batch-{ACCOUNT}-874"
            s3.create_bucket(Bucket=BUCKET)
            log(f"✅ S3 bucket '{BUCKET}' created")
        else:
            raise

# ═══════════════════════════════════════════════════════════════
# STEP 2: Upload raw data and PySpark script to S3
# ═══════════════════════════════════════════════════════════════
def upload_to_s3():
    s3 = session.client("s3")
    base = "/home/keni_garcia/Documents/backend-aerolinea"

    files_to_upload = [
        (f"{base}/raw/flights.csv", "raw/flights.csv"),
        (f"{base}/raw/reservations.csv", "raw/reservations.csv"),
        (f"{base}/scripts/emr_job.py", "scripts/emr_job.py"),
    ]

    for local, key in files_to_upload:
        size_mb = os.path.getsize(local) / (1024 * 1024)
        log(f"   Uploading {key} ({size_mb:.1f} MB)...")
        s3.upload_file(local, BUCKET, key)

    log("✅ All files uploaded to S3")

# ═══════════════════════════════════════════════════════════════
# STEP 3: Launch EMR cluster (auto-terminate)
# ═══════════════════════════════════════════════════════════════
def launch_emr():
    emr = session.client("emr")

    # Get default subnet
    ec2 = session.client("ec2")
    subnets = ec2.describe_subnets(Filters=[{"Name": "default-for-az", "Values": ["true"]}])["Subnets"]
    subnet_id = subnets[0]["SubnetId"] if subnets else None
    log(f"   Using subnet: {subnet_id}")

    ec2_attrs = {"InstanceProfile": "EMR_EC2_DefaultRole"}
    if subnet_id:
        ec2_attrs["SubnetId"] = subnet_id

    response = emr.run_job_flow(
        Name="AirlineBatch-Seed874",
        ReleaseLabel="emr-6.15.0",
        Applications=[{"Name": "Spark"}],
        ServiceRole="EMR_DefaultRole",
        JobFlowRole="EMR_EC2_DefaultRole",
        Instances={
            "InstanceGroups": [
                {"Name": "Master", "Market": "ON_DEMAND", "InstanceRole": "MASTER",
                 "InstanceType": "m4.large", "InstanceCount": 1},
                {"Name": "Core", "Market": "ON_DEMAND", "InstanceRole": "CORE",
                 "InstanceType": "m4.large", "InstanceCount": 2},
            ],
            "Ec2SubnetId": subnet_id,
            "KeepJobFlowAliveWhenNoSteps": False,  # auto-terminate
        },
        Steps=[{
            "Name": "PySparkCleaning",
            "ActionOnFailure": "TERMINATE_CLUSTER",
            "HadoopJarStep": {
                "Jar": "command-runner.jar",
                "Args": [
                    "spark-submit", "--deploy-mode", "cluster",
                    f"s3://{BUCKET}/scripts/emr_job.py",
                    f"s3://{BUCKET}/raw",
                    f"s3://{BUCKET}/curated"
                ]
            }
        }],
        LogUri=f"s3://{BUCKET}/emr-logs/",
        VisibleToAllUsers=True,
    )

    cluster_id = response["JobFlowId"]
    log(f"✅ EMR Cluster launched: {cluster_id}")
    return cluster_id

# ═══════════════════════════════════════════════════════════════
# STEP 4: Get default VPC security group info
# ═══════════════════════════════════════════════════════════════
def get_default_vpc_info():
    ec2 = session.client("ec2")
    vpcs = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])["Vpcs"]
    vpc_id = vpcs[0]["VpcId"]
    
    sgs = ec2.describe_security_groups(Filters=[
        {"Name": "vpc-id", "Values": [vpc_id]},
        {"Name": "group-name", "Values": ["default"]}
    ])["SecurityGroups"]
    default_sg = sgs[0]["GroupId"]

    subnets = ec2.describe_subnets(Filters=[
        {"Name": "vpc-id", "Values": [vpc_id]},
        {"Name": "default-for-az", "Values": ["true"]}
    ])["Subnets"]
    subnet_id = subnets[0]["SubnetId"]
    
    log(f"   VPC: {vpc_id}, Default SG: {default_sg}, Subnet: {subnet_id}")
    return vpc_id, default_sg, subnet_id

# ═══════════════════════════════════════════════════════════════
# STEP 5: Create Security Group for backend
# ═══════════════════════════════════════════════════════════════
def create_security_group(vpc_id):
    ec2 = session.client("ec2")
    
    try:
        resp = ec2.create_security_group(
            GroupName="airline-backend-sg",
            Description="Security group for airline backend (ports 22, 8000, 5432)",
            VpcId=vpc_id
        )
        sg_id = resp["GroupId"]
        log(f"   Created SG: {sg_id}")
    except ec2.exceptions.ClientError as e:
        if "InvalidGroup.Duplicate" in str(e):
            sgs = ec2.describe_security_groups(Filters=[
                {"Name": "group-name", "Values": ["airline-backend-sg"]},
                {"Name": "vpc-id", "Values": [vpc_id]}
            ])["SecurityGroups"]
            sg_id = sgs[0]["GroupId"]
            log(f"   SG already exists: {sg_id}")
            return sg_id
        raise

    # Open ports
    for port in [22, 8000, 5432]:
        try:
            ec2.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[{
                    "IpProtocol": "tcp", "FromPort": port, "ToPort": port,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}]
                }]
            )
        except Exception:
            pass

    log(f"✅ Security Group configured: {sg_id} (ports 22, 8000, 5432)")
    return sg_id

# ═══════════════════════════════════════════════════════════════
# STEP 6: Create RDS PostgreSQL instance
# ═══════════════════════════════════════════════════════════════
def create_rds(sg_id):
    rds = session.client("rds")

    try:
        resp = rds.create_db_instance(
            DBInstanceIdentifier="airline-db",
            DBInstanceClass="db.t3.micro",
            Engine="postgres",
            EngineVersion="16.4",
            MasterUsername="postgres",
            MasterUserPassword="ClaveLocal123",
            AllocatedStorage=20,
            StorageType="gp2",
            DBName="sistema_reservas",
            PubliclyAccessible=True,
            MultiAZ=False,  # R11: prohibido Multi-AZ
            VpcSecurityGroupIds=[sg_id],
            BackupRetentionPeriod=0,  # no backups to save cost
        )
        log(f"✅ RDS instance 'airline-db' creation started (db.t3.micro, Single-AZ)")
    except rds.exceptions.DBInstanceAlreadyExistsFault:
        log("✅ RDS instance 'airline-db' already exists")

# ═══════════════════════════════════════════════════════════════
# STEP 7: Create EC2 instance for backend
# ═══════════════════════════════════════════════════════════════
def create_ec2(sg_id, subnet_id):
    ec2 = session.client("ec2")

    # Find Ubuntu 24.04 AMI
    images = ec2.describe_images(
        Owners=["099720109477"],  # Canonical
        Filters=[
            {"Name": "name", "Values": ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]},
            {"Name": "state", "Values": ["available"]},
        ]
    )["Images"]
    
    if not images:
        # Try Amazon Linux 2023
        images = ec2.describe_images(
            Owners=["amazon"],
            Filters=[
                {"Name": "name", "Values": ["al2023-ami-2023*-x86_64"]},
                {"Name": "state", "Values": ["available"]},
            ]
        )["Images"]
    
    images.sort(key=lambda x: x["CreationDate"], reverse=True)
    ami_id = images[0]["ImageId"]
    log(f"   Using AMI: {ami_id} ({images[0]['Name'][:60]})")

    # User data script to install everything and start the app
    user_data = f"""#!/bin/bash
set -ex
exec > /var/log/user-data.log 2>&1

apt-get update -y
apt-get install -y python3-pip python3-venv git postgresql-client

cd /home/ubuntu
git clone https://github.com/kngarcia/backend-aerolinea.git || true
cd backend-aerolinea

python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn psycopg2-binary pydantic pydantic-settings boto3

# Wait for RDS to be available (up to 10 min)
for i in $(seq 1 60); do
    RDS_HOST=$(aws rds describe-db-instances --db-instance-identifier airline-db --query 'DBInstances[0].Endpoint.Address' --output text --region us-east-1 2>/dev/null || echo "")
    if [ -n "$RDS_HOST" ] && [ "$RDS_HOST" != "None" ]; then
        echo "RDS is at $RDS_HOST"
        break
    fi
    echo "Waiting for RDS... attempt $i"
    sleep 10
done

# Create tables on RDS
python3 -c "
import psycopg2
conn = psycopg2.connect(host='$RDS_HOST', port=5432, dbname='sistema_reservas', user='postgres', password='ClaveLocal123')
cur = conn.cursor()
cur.execute('''
CREATE TABLE IF NOT EXISTS flights (
    flight_id VARCHAR(100) PRIMARY KEY,
    route VARCHAR(20) NOT NULL,
    origin VARCHAR(10) NOT NULL,
    destination VARCHAR(10) NOT NULL,
    flight_date VARCHAR(20) NOT NULL,
    capacity INT NOT NULL,
    seats_available INT NOT NULL CHECK (seats_available >= 0),
    price_cents BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_flights_search ON flights (origin, destination, flight_date);
CREATE TABLE IF NOT EXISTS reservations (
    reservation_id SERIAL PRIMARY KEY,
    flight_id VARCHAR(100) NOT NULL REFERENCES flights(flight_id),
    passenger_name VARCHAR(255) NOT NULL,
    fare_class VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT (chr(67)||chr(79)||chr(78)||chr(70)||chr(73)||chr(82)||chr(77)||chr(69)||chr(68)),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_reservations_flight ON reservations (flight_id);
''')
conn.commit()
cur.close()
conn.close()
print('Tables created on RDS!')
" || echo "Table creation will be done manually"

export DB_HOST=$RDS_HOST
export DB_PORT=5432
export DB_USER=postgres
export DB_PASSWORD=ClaveLocal123
export DB_NAME=sistema_reservas
export ATHENA_DATABASE=airline_analytics
export ATHENA_OUTPUT="s3://{BUCKET}/athena-results/"
export AWS_DEFAULT_REGION=us-east-1

nohup venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 > /home/ubuntu/app.log 2>&1 &
echo "Backend started on port 8000"
"""

    # Check if instance already exists
    existing = ec2.describe_instances(Filters=[
        {"Name": "tag:Name", "Values": ["Airline-Backend"]},
        {"Name": "instance-state-name", "Values": ["pending", "running"]}
    ])["Reservations"]
    
    if existing and existing[0]["Instances"]:
        inst = existing[0]["Instances"][0]
        log(f"✅ EC2 instance already running: {inst['InstanceId']} ({inst.get('PublicIpAddress', 'pending IP')})")
        return inst["InstanceId"]

    # Find LabInstanceProfile
    iam = session.client("iam")
    profile_name = "LabInstanceProfile"
    try:
        iam.get_instance_profile(InstanceProfileName=profile_name)
    except Exception:
        profile_name = "EMR_EC2_DefaultRole"

    response = ec2.run_instances(
        ImageId=ami_id,
        InstanceType="t3.small",  # R11 compliant
        MinCount=1, MaxCount=1,
        KeyName="vockey",
        SecurityGroupIds=[sg_id],
        SubnetId=subnet_id,
        IamInstanceProfile={"Name": profile_name},
        UserData=user_data,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": "Airline-Backend"}]
        }],
    )

    instance_id = response["Instances"][0]["InstanceId"]
    log(f"✅ EC2 instance launched: {instance_id} (t3.small)")
    return instance_id


# ═══════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    log("🚀 Starting full AWS deployment...")
    
    # Step 1: S3
    log("── STEP 1: Creating S3 bucket ──")
    create_bucket()

    # Step 2: Upload data
    log("── STEP 2: Uploading raw data + PySpark script ──")
    upload_to_s3()

    # Step 3: EMR
    log("── STEP 3: Launching EMR cluster ──")
    cluster_id = launch_emr()

    # Step 4-5: VPC + Security Group
    log("── STEP 4-5: Configuring networking ──")
    vpc_id, default_sg, subnet_id = get_default_vpc_info()
    sg_id = create_security_group(vpc_id)

    # Step 6: RDS
    log("── STEP 6: Creating RDS PostgreSQL ──")
    create_rds(sg_id)

    # Step 7: EC2
    log("── STEP 7: Launching EC2 backend ──")
    instance_id = create_ec2(sg_id, subnet_id)

    log("")
    log("═" * 60)
    log("🎉 ALL AWS RESOURCES LAUNCHED SUCCESSFULLY!")
    log(f"   S3 Bucket:  {BUCKET}")
    log(f"   EMR Cluster: {cluster_id}")
    log(f"   EC2 Instance: {instance_id}")
    log(f"   RDS Instance: airline-db")
    log("═" * 60)
    log("")
    log("⏳ NEXT: Wait ~8-10 min for EMR to finish and RDS to be available.")
    log("   Then run the Athena table creation and final pytest.")
