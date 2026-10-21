#!/bin/bash
# ====================================================================
# GUÍA DE COMANDOS AWS CLI - SEGUNDO CORTE
# Big Data and Data Engineering - Airline Reservation System
# Seed Asignado: 874
# ====================================================================

# 1. Definir variables (¡Ajustar BUCKET y SUBNET según tu Learner Lab!)
export BUCKET_NAME="airline-analytics-team-874"
export REGION="us-east-1"
export SUBNET_ID="subnet-xxxxxxxx" # Subred pública del Learner Lab
export KEY_NAME="vockey"           # KeyPair default de Learner Lab

echo "=== 1. Crear Bucket S3 y Subir Archivos ==="
aws s3 mb s3://$BUCKET_NAME --region $REGION

# Subir datos crudos generados (2M filas)
aws s3 cp raw/ s3://$BUCKET_NAME/raw/ --recursive

# Subir script PySpark
aws s3 cp scripts/emr_job.py s3://$BUCKET_NAME/scripts/emr_job.py

echo "=== 2. Lanzar Clúster EMR Transitorio con Auto-Terminate ==="
# Cumple con R4, R10 y R11:
# - Solo instancia m4.large (permitida en Learner Lab)
# - --auto-terminate garantiza que se apague al terminar el step (R10)
# - Genera las 24 particiones con timestamp verificado durante la ejecución
aws emr create-cluster \
  --name "Airline-PySpark-Batch-874" \
  --release-label emr-6.15.0 \
  --applications Name=Spark \
  --service-role EMR_DefaultRole \
  --ec2-attributes InstanceProfile=EMR_EC2_DefaultRole,KeyName=$KEY_NAME,SubnetId=$SUBNET_ID \
  --instance-type m4.large \
  --instance-count 3 \
  --auto-terminate \
  --steps Type=Spark,Name="AirlineCleaningAndMetrics",ActionOnFailure=TERMINATE_CLUSTER,Args=[--deploy-mode,cluster,s3://$BUCKET_NAME/scripts/emr_job.py,s3://$BUCKET_NAME/raw,s3://$BUCKET_NAME/curated] \
  --region $REGION

echo "=== 3. Tablas en Glue / Athena ==="
# Una vez el clúster pase a estado COMPLETED:
# Ejecuta en la consola de Athena o vía AWS CLI el script 'scripts/create_athena_tables.sql'
# reemplazando REEMPLAZAR_CON_TU_BUCKET por '$BUCKET_NAME'.

