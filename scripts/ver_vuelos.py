"""Consulta la tabla flights del RDS ejecutando psql en la EC2 via SSM.
El password lo lee la propia instancia de SSM Parameter Store: nunca pasa por aqui.
"""
import time

import boto3

INSTANCE = "i-07891ecc7268f25e5"
REGION = "us-east-1"
# El endpoint se pregunta a la API: si el RDS se recreara, el valor fijo quedaria obsoleto.
HOST = boto3.client("rds", region_name=REGION).describe_db_instances(
    DBInstanceIdentifier="airline-db")["DBInstances"][0]["Endpoint"]["Address"]

SQL = (
    "SELECT origin, destination, flight_date, count(*) AS vuelos, "
    "sum(seats_available) AS asientos_libres "
    "FROM flights WHERE seats_available > 0 "
    "GROUP BY origin, destination, flight_date "
    "ORDER BY asientos_libres DESC, flight_date LIMIT 25;"
)

SHELL = [
    "export PGPASSWORD=$(aws ssm get-parameter --name /airline/db_password "
    "--with-decryption --query Parameter.Value --output text --region " + REGION + ")",
    "psql -h " + HOST + " -U postgres -d sistema_reservas -c \"" + SQL + "\"",
    "psql -h " + HOST + " -U postgres -d sistema_reservas -c "
    "\"SELECT count(*) AS total_vuelos, sum(seats_available) AS total_asientos FROM flights;\"",
]

ssm = boto3.client("ssm", region_name=REGION)
cid = ssm.send_command(
    InstanceIds=[INSTANCE],
    DocumentName="AWS-RunShellScript",
    Parameters={"commands": SHELL},
)["Command"]["CommandId"]

for _ in range(40):
    time.sleep(2)
    inv = ssm.get_command_invocation(CommandId=cid, InstanceId=INSTANCE)
    if inv["Status"] not in ("Pending", "InProgress", "Delayed"):
        break

print("estado:", inv["Status"])
print(inv.get("StandardOutputContent", ""))
err = inv.get("StandardErrorContent", "").strip()
if err:
    print("--- stderr ---")
    print(err[:1500])
