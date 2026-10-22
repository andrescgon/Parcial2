#!/bin/bash
# Rehace TODO el camino analitico con una semilla nueva.
#
#   bash scripts/rerun_seed.sh 1234
#
# Tarda unos 25 minutos, casi todos esperando a que EMR arranque.
# No toca la EC2 ni el RDS: la base transaccional no depende de la semilla.
set -euo pipefail

SEED="${1:-}"
if [ -z "$SEED" ]; then
  echo "Uso: bash scripts/rerun_seed.sh <SEMILLA>" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source scripts/env.sh
export ATHENA_OUTPUT REGION ATHENA_DATABASE

say() { echo ""; echo "=== $* ==="; }

# ---------------------------------------------------------------- 0. credenciales
say "0/7  Comprobando credenciales"
if ! aws sts get-caller-identity --query Account --output text; then
  echo "SIN CREDENCIALES. Abre el Learner Lab, AWS Details -> AWS CLI -> Show," >&2
  echo "y pega el bloque en ~/.aws/credentials. Luego vuelve a lanzar esto." >&2
  exit 1
fi

# ---------------------------------------------------------------- 1. datos crudos
say "1/7  Generando los datos con la semilla $SEED"
rm -rf raw raw_sample
python -m airline_data.generate --seed "$SEED" --rows 2000000 --out raw/
python -m airline_data.generate --seed "$SEED" --rows 20000 --out raw_sample/

# ------------------------------------------------------------------------ 2. S3
say "2/7  Subiendo a S3 y borrando el Parquet viejo"
# Se borra curated/ a proposito: si quedaran archivos de la semilla anterior,
# Athena contaria filas de las dos y R4 fallaria.
aws s3 rm "s3://$BUCKET/curated/" --recursive --only-show-errors || true
aws s3 rm "s3://$BUCKET/curated-sample/" --recursive --only-show-errors || true
aws s3 cp raw/ "s3://$BUCKET/raw/" --recursive --only-show-errors
aws s3 cp raw_sample/ "s3://$BUCKET/raw-sample/" --recursive --only-show-errors
aws s3 cp scripts/emr_job.py "s3://$BUCKET/scripts/emr_job.py" --only-show-errors

# ----------------------------------------------------------------------- 3. EMR
say "3/7  Lanzando EMR (3 x m4.large, auto-terminate)"
SUBNET=$(aws ec2 describe-subnets --filters Name=default-for-az,Values=true \
  --query 'Subnets[0].SubnetId' --output text --region "$REGION")

STEPS=$(cat <<JSON
[{"Name":"SmokeTestMuestra","Type":"Spark","ActionOnFailure":"TERMINATE_CLUSTER",
  "Args":["--deploy-mode","cluster","s3://$BUCKET/scripts/emr_job.py","s3://$BUCKET/raw-sample","s3://$BUCKET/curated-sample"]},
 {"Name":"LimpiezaYMetricasCompleto","Type":"Spark","ActionOnFailure":"TERMINATE_CLUSTER",
  "Args":["--deploy-mode","cluster","s3://$BUCKET/scripts/emr_job.py","s3://$BUCKET/raw","s3://$BUCKET/curated"]}]
JSON
)

CLUSTER=$(aws emr create-cluster \
  --name "airline-batch-$SEED" \
  --release-label emr-6.15.0 \
  --applications Name=Spark \
  --service-role EMR_DefaultRole \
  --ec2-attributes "InstanceProfile=EMR_EC2_DefaultRole,KeyName=vockey,SubnetId=$SUBNET" \
  --instance-groups InstanceGroupType=MASTER,InstanceCount=1,InstanceType=m4.large \
                    InstanceGroupType=CORE,InstanceCount=2,InstanceType=m4.large \
  --auto-terminate \
  --steps "$STEPS" \
  --log-uri "s3://$BUCKET/emr-logs/" \
  --region "$REGION" \
  --query ClusterId --output text)

echo "Cluster: $CLUSTER   (se apaga solo al terminar)"
echo "Esperando. Son unos 20 minutos; no cierres esta ventana."
aws emr wait cluster-terminated --cluster-id "$CLUSTER" --region "$REGION"

say "4/7  Resultado de los steps"
aws emr list-steps --cluster-id "$CLUSTER" --region "$REGION" \
  --query 'Steps[].[Name,Status.State]' --output text
FALLOS=$(aws emr list-steps --cluster-id "$CLUSTER" --region "$REGION" \
  --query 'Steps[?Status.State!=`COMPLETED`].Name' --output text)
if [ -n "$FALLOS" ]; then
  echo "EMR FALLO en: $FALLOS" >&2
  echo "Mira el log:  aws s3 ls s3://$BUCKET/emr-logs/$CLUSTER/steps/ --recursive" >&2
  exit 1
fi

# ---------------------------------------------------------------------- 5. Glue
say "5/7  Registrando las particiones en Glue"
python scripts/athena_run.py "MSCK REPAIR TABLE reservations_curated"

# ------------------------------------------------------------------ 6. verificar
say "6/7  Comprobando contra el oraculo"
ESPERADO=$(python -c "from airline_data.oracle import load_truth; print(load_truth($SEED, 2000000).row_count)")
OBTENIDO=$(python scripts/athena_run.py "SELECT count(*) FROM reservations_curated" | tail -1 | tr -d ' |')
echo "esperado: $ESPERADO    obtenido: $OBTENIDO"
if [ "$ESPERADO" != "$OBTENIDO" ]; then
  echo "NO COINCIDE. Revisa que curated/ se haya borrado antes del run." >&2
  exit 1
fi

# -------------------------------------------------------------------- 7. config
say "7/7  Actualizando config.yaml"
python -c "
import pathlib, re, sys
p = pathlib.Path('config.yaml'); s = p.read_text(encoding='utf-8')
p.write_text(re.sub(r'^seed:.*$', 'seed: ' + sys.argv[1], s, flags=re.M), encoding='utf-8')
print(open('config.yaml', encoding='utf-8').read())
" "$SEED"

cat <<FIN

LISTO. El camino analitico esta rehecho con la semilla $SEED.

Falta solo:
  1. Comprobar que la IP de config.yaml es la de la EC2 ahora mismo:
       aws ec2 describe-instances --instance-ids i-07891ecc7268f25e5 \\
         --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
  2. Correr el harness:
       python -m pytest
FIN
