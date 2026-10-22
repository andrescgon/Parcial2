# Unica fuente de verdad de los parametros del despliegue. Hacer: source scripts/env.sh
export SEED=3604
export REGION=us-east-1
export BUCKET=airline-analytics-3604-723400800674
export ATHENA_DATABASE=airline_analytics
export ATHENA_OUTPUT="s3://${BUCKET}/athena-results/"
# La contrasena de RDS NO va aqui: se exporta a mano antes de desplegar.
#   export DB_PASSWORD='...'
