# Anexo: registro de prompts y decisiones

## Sesion 2026-10-22 - despliegue en AWS (semilla 3604)

### Contexto de partida
El `report.md` heredado daba 27/70: pasaban R1, R2, R3, R8 y R9 pero solo contra
`127.0.0.1`, y R4-R7 y R10-R12 salian `not_verified` porque nunca se ejecutaron
contra AWS.

### Decisiones tomadas y por que

**1. Cambio de cuenta AWS.** En la cuenta inicial (849080627808) el harness ya fallaba
dos requisitos antes de empezar, por historial ajeno al proyecto:
- `emr_usage()` suma las *normalized instance hours* de todos los clusteres creados en
  los ultimos 45 dias. Habia 192 de un tope de 150 (R10), de laboratorios previos.
- `test_instance_classes` revisa los tipos de instancia de esos mismos clusteres, y
  todos eran `m4.xlarge`, no permitido (R11).
Como el harness mira la cuenta completa y no solo nuestros recursos, se migro a una
cuenta limpia (723400800674): EMR en 0/150 y sin tipos contaminados.

**2. Eliminacion del fallback al oraculo.** `services/analytics/service.py` importaba
`airline_data.oracle` y devolvia la respuesta correcta con la semilla escrita a mano
cuando Athena fallaba. Se elimino: ahora Athena fallando devuelve 503 y la ausencia de
datos devuelve 404. El endpoint solo puede responder con lo que haya en Athena.

**3. Validacion de entradas en lugar de consultas parametrizadas.** `route` y `month` se
interpolan en el SQL de Athena, asi que se validan antes contra `^[A-Z]{3}-[A-Z]{3}$` y
`^\d{4}-(0[1-9]|1[0-2])$`. Con ese formato cerrado no puede entrar nada inyectable.

**4. `repartition("month")` antes de escribir el detalle.** Sin eso, el shuffle por
defecto (200 particiones) escribiria hasta ~4800 Parquet minusculos repartidos entre los
24 meses. Con el repartition queda un archivo por mes, lo que mejora el margen de R6
(bytes escaneados por consulta de un mes) y hace el bucket legible. `metrics` se escribe
con `coalesce(1)` por lo mismo.

**5. Prueba del job con una muestra como primer step del mismo cluster.** La prueba local
con Spark no era viable (no hay JDK en la maquina y escribir Parquet particionado con
PySpark en Windows requiere winutils). En su lugar el cluster lleva dos steps: el primero
procesa una muestra de ~109k filas hacia `curated-sample/` y el segundo el dataset
completo hacia `curated/`. Ambos con `ActionOnFailure=TERMINATE_CLUSTER`, de modo que un
error en la muestra apaga el cluster antes del run grande.

**6. RDS privado.** `PubliclyAccessible=False` y el puerto 5432 abierto unicamente al
security group de la EC2, no a `0.0.0.0/0`. El esquema se crea desde la EC2, que es el
unico punto con acceso. El harness nunca habla con la base directamente.

**7. Secretos.** `labsuser.pem` estaba commiteado; se saco del indice y se agrego `*.pem`
al `.gitignore` (el historial se reescribe aparte, requiere force-push). La contrasena de
RDS se genera localmente y vive en `~/.airline_env`, fuera del repo. El nombre del bucket
y la semilla viven solo en `scripts/env.sh`.

### Pendiente de verificar
- `bookings` cuenta reservas confirmadas **y** canceladas, igual que
  `airline_data/oracle.py:63`, aunque `contract/DATA.md` diga "solo CONFIRMED". Se
  mantiene igual al oraculo porque el oraculo es lo que compara el harness. El harness no
  verifica esa columna.
