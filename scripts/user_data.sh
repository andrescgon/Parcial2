#!/bin/bash
# Arranque de la EC2 del backend. Amazon Linux 2023 (trae aws cli y python3.11).
# El codigo se baja de S3 con el rol de la instancia: no hace falta clonar GitHub.
set -x
exec > /var/log/airline-deploy.log 2>&1

BUCKET="__BUCKET__"
REGION="us-east-1"

dnf install -y python3-pip python3-devel gcc postgresql16

mkdir -p /opt/airline && cd /opt/airline
aws s3 cp "s3://${BUCKET}/app/app.tar.gz" /tmp/app.tar.gz --region "$REGION"
tar xzf /tmp/app.tar.gz -C /opt/airline
pip3 install -r /opt/airline/scripts/requirements-server.txt

# El password NO va en el user-data: los metadatos de la instancia son legibles desde
# dentro de ella. Se lee de SSM Parameter Store cifrado, con reintentos por si el
# parametro se crea despues del arranque.
for i in $(seq 1 60); do
  DB_PASSWORD=$(aws ssm get-parameter --name /airline/db_password --with-decryption --query Parameter.Value --output text --region "$REGION" 2>/dev/null)
  if [ -n "$DB_PASSWORD" ] && [ "$DB_PASSWORD" != "None" ]; then break; fi
  sleep 10
done

# Esperar a que el RDS este disponible (hasta 15 min)
for i in $(seq 1 90); do
  RDS_HOST=$(aws rds describe-db-instances --db-instance-identifier airline-db --query 'DBInstances[0].Endpoint.Address' --output text --region "$REGION" 2>/dev/null)
  ST=$(aws rds describe-db-instances --db-instance-identifier airline-db --query 'DBInstances[0].DBInstanceStatus' --output text --region "$REGION" 2>/dev/null)
  if [ -n "$RDS_HOST" ] && [ "$RDS_HOST" != "None" ] && [ "$ST" = "available" ]; then break; fi
  sleep 10
done
echo "RDS=$RDS_HOST estado=$ST"

export PGPASSWORD="$DB_PASSWORD"
psql -h "$RDS_HOST" -U postgres -d sistema_reservas -f /opt/airline/scripts/schema.sql

cat > /etc/systemd/system/airline.service <<UNIT
[Unit]
Description=Airline backend (FastAPI)
After=network-online.target

[Service]
WorkingDirectory=/opt/airline
Environment=DB_HOST=${RDS_HOST}
Environment=DB_PORT=5432
Environment=DB_NAME=sistema_reservas
Environment=DB_USER=postgres
Environment=DB_PASSWORD=${DB_PASSWORD}
Environment=AWS_REGION=${REGION}
Environment=AWS_DEFAULT_REGION=${REGION}
Environment=ATHENA_DATABASE=airline_analytics
Environment=ATHENA_WORKGROUP=primary
Environment=ATHENA_OUTPUT=s3://${BUCKET}/athena-results/
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always

[Install]
WantedBy=multi-user.target
UNIT

chmod 600 /etc/systemd/system/airline.service
systemctl daemon-reload
systemctl enable --now airline.service
sleep 8
curl -s localhost:8000/health && echo " backend arriba"
