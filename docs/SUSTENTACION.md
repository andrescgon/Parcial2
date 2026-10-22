# Guia de emergencia para la sustentacion

Todo lo que puede hacer falta en vivo, sin tener que recordar nada.

## Datos del despliegue

| Cosa | Valor |
|---|---|
| Cuenta AWS | 723400800674 (us-east-1) |
| EC2 | `i-07891ecc7268f25e5` (t3.small) |
| RDS | `airline-db` (db.t3.micro, privado) |
| Bucket | `airline-analytics-3604-723400800674` |
| Base Athena/Glue | `airline_analytics` |
| Semilla actual | ver `config.yaml` |

Antes de cualquier cosa, credenciales frescas en `~/.aws/credentials`
(Learner Lab -> AWS Details -> AWS CLI -> Show).

---

## 1. "Cambie la semilla y vuelva a correr todo"

```bash
bash scripts/rerun_seed.sh <NUEVA_SEMILLA>
```

Tarda unos 25 minutos, casi todos esperando a EMR. Hace, en orden: genera los
datos, borra el Parquet viejo de S3, sube el nuevo crudo, lanza un clúster EMR
con dos steps (muestra y completo), espera a que termine, registra las
particiones con `MSCK REPAIR`, compara el conteo contra el oráculo y actualiza
`config.yaml`. Si algo falla se detiene y dice dónde.

**No hace falta tocar la EC2 ni el RDS**: la base transaccional no depende de la
semilla, solo guarda los vuelos que crea el propio harness.

Al terminar:

```bash
python -m pytest
```

### Por qué se borra `curated/` antes

Si quedaran Parquet de la semilla anterior, Athena sumaría las filas de ambas y
el conteo de R4 no cuadraría. El job escribe con `mode("overwrite")` y
`partitionOverwriteMode=dynamic`, que en teoría reemplaza cada partición, pero
borrar primero es determinista y cuesta un segundo.

---

## 2. "Cambie una regla de limpieza"

El script que corre EMR es **la copia que está en S3**, no la de tu disco. El
ciclo completo es:

```bash
# 1. editar scripts/emr_job.py
# 2. subirlo
aws s3 cp scripts/emr_job.py s3://$BUCKET/scripts/emr_job.py
# 3. relanzar (reutiliza todo lo demas)
bash scripts/rerun_seed.sh <LA_MISMA_SEMILLA>
```

Si cambias una regla de limpieza, el resultado **dejará de coincidir con el
oráculo del profesor** y R4 fallará: eso es lo esperado y hay que decirlo. El
oráculo vive en `airline_data/oracle.py` y es la definición de "correcto".

---

## 3. Consultas de Athena en vivo

```bash
python scripts/athena_run.py "SELECT count(*) FROM reservations_curated"
python scripts/athena_run.py "SHOW PARTITIONS reservations_curated"
python scripts/athena_run.py "SELECT route, CAST(sum(seats_sold) AS DOUBLE)/sum(seats_capacity) AS occ FROM route_month_metrics GROUP BY route ORDER BY occ DESC LIMIT 10"
```

**Para demostrar la poda de particiones** (imprime los bytes escaneados):

```bash
python scripts/athena_run.py "SELECT count(*) FROM reservations_curated WHERE month='2024-01'"
python scripts/athena_run.py "SELECT count(*) FROM reservations_curated"
```

La primera escanea ~305 KB, la segunda barre las 24 particiones. Esa diferencia
es el argumento entero de por qué se particiona por mes.

---

## 4. Si el backend no responde

La EC2 está registrada en SSM, así que se le pueden mandar comandos **sin SSH**
y sin abrir el puerto 22.

```bash
# ver si el servicio esta vivo
aws ssm send-command --instance-ids i-07891ecc7268f25e5 \
  --document-name AWS-RunShellScript \
  --parameters 'commands=["systemctl status airline --no-pager | head -20"]' \
  --query Command.CommandId --output text

# leer la salida (usa el CommandId que devolvio el anterior)
aws ssm get-command-invocation --instance-id i-07891ecc7268f25e5 \
  --command-id <COMMAND_ID> --query StandardOutputContent --output text

# reiniciar el backend
aws ssm send-command --instance-ids i-07891ecc7268f25e5 \
  --document-name AWS-RunShellScript \
  --parameters 'commands=["systemctl restart airline"]'

# ver el log del arranque inicial
aws ssm send-command --instance-ids i-07891ecc7268f25e5 \
  --document-name AWS-RunShellScript \
  --parameters 'commands=["tail -50 /var/log/airline-deploy.log"]'
```

---

## 5. Si la IP cambio (pasa cada vez que se reinicia el lab)

```bash
aws ec2 start-instances --instance-ids i-07891ecc7268f25e5
aws rds start-db-instance --db-instance-identifier airline-db
# esperar ~2 min y pedir la IP nueva
aws ec2 describe-instances --instance-ids i-07891ecc7268f25e5 \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text
```

Luego cambiar **las dos** `base_url` de `config.yaml` (backend y frontend) por
esa IP, y hacer commit y push para que el profesor corra con la URL correcta.

---

## 6. Comprobaciones rapidas antes de que el profesor ejecute

```bash
aws emr list-clusters --active                     # tiene que salir vacio (R10)
curl http://<IP>:8000/health                       # {"status":"ok"}
grep base_url config.yaml                          # la IP de ahora
python scripts/athena_run.py "SELECT count(*) FROM reservations_curated"
```

---

## 7. Al terminar: apagar

```bash
aws ec2 stop-instances --instance-ids i-07891ecc7268f25e5
aws rds stop-db-instance --db-instance-identifier airline-db
```

Encendidos cuestan unos 0,04 USD/hora contra el presupuesto de 50.
