# SEGUNDO CORTE: Airline Reservation System - Managerial Analytics Panel
**Big Data and Data Engineering**  
**Estudiantes:** Kevin Nicolai García Rodríguez & Andrés Castro Gonzáles  
**Universidad Sergio Arboleda - Escuela de Ciencias Exactas e Ingeniería**  
**Seed Asignado:** 874  

---

## 5. Decisiones Arquitectónicas y Justificación (Well-Architected)

### 5.1. Hosting Model (Modelo de Alojamiento)
El backend (FastAPI) y el frontend interactivo (SPA en HTML/JS) se alojan juntos en una única instancia virtual **Amazon EC2 tipo `t3.small`** en subred pública con Security Groups restringidos, conectada a una base de datos **Amazon RDS PostgreSQL tipo `db.t3.micro`** (Single-AZ, 20 GB almacenamiento SSD GP2).

* **¿Por qué no una opción más gestionada (Serverless tipo ECS/Lambda)?**  
  Para el alcance de la prueba de concurrencia extrema (50 hilos simultáneos liberados por barrera en **R2** y 20 clientes concurrentes en **R1**), las arquitecturas serverless con Lambda sufren de arranques en frío (*cold starts*) y límites de conexión simultánea a bases de datos relacionales sin un RDS Proxy (que añadiría un costo fijo de ~$15 USD/mes, violando el presupuesto de $50 USD en **R12**).
* **¿Por qué no una opción menos gestionada (EC2 con PostgreSQL autogestionado)?**  
  RDS automatiza la recuperación ante fallos del motor, rotación de logs y aprovisionamiento seguro de almacenamiento, satisfaciendo el pilar de **Operational Excellence** y **Reliability** sin infringir el límite de costos.
* **Costo mínimo garantizado (R1, R2, R11):**  
  La combinación EC2 `t3.small` ($15.18 USD/mes) + RDS `db.t3.micro` ($14.50 USD/mes) suma ~$29.68 USD/mes, cumpliendo holgadamente el límite de $50 USD de AWS Learner Lab y asegurando latencias p95 < 0.1 s para búsquedas y actualización atómica sin sobreventa.  
  *Pilares Well-Architected:* **Cost Optimization**, **Performance Efficiency**, **Reliability**.

---

### 5.2. Por qué EMR en este Proyecto (Why EMR Here)
El procesamiento batch de 2 millones de filas de historial de reservas con datos deliberadamente corruptos requiere transformaciones complejas (limpieza de espacios, filtrado condicional multivalor, deduplicación global y agregación multidimensional).

* **¿Qué hace el job de EMR (PySpark) que Athena solo no puede hacer eficientemente?**  
  Athena es un motor de consulta SQL serverless de solo lectura (*read-mostly analytics*), no un motor de transformación de propósito general. Aunque Athena permite CTAS (*Create Table As Select*), no ofrece el control granular de ordenamiento distribuido y deduplicación por primera ocurrencia de `reservation_id` (**C5**), ni optimización de particionamiento con control de número de archivos pequeños en S3. PySpark distribuye el trabajo en la memoria RAM del clúster mediante DAGs optimizados (Catalyst Optimizer), garantizando la integridad de las reglas **C1 a C5**.
* **Alternativas consideradas:**  
  - *AWS Glue Job:* Excelente alternativa serverless, pero tiene un tiempo de inicialización de clúster de ~3 minutos y una tarificación por DPU mínima por ejecución.  
  - *Athena CTAS:* Escanea grandes volúmenes de texto plano en cada intento de transformación, generando costos de $5 USD por TB escaneado sobre datos sin comprimir.
* **Opción EMR elegida y garantía de apagado (R4, R10):**  
  Se configuró un clúster **EMR en modo Step con `--auto-terminate`**, utilizando 3 nodos tipo **`m4.large`** (único tipo de cómputo para EMR permitido en el Learner Lab según **R11**). Al finalizar el procesamiento de los pasos (ActionOnFailure=TERMINATE_CLUSTER), el clúster se apaga y destruye automáticamente, garantizando que el uso de horas normalizadas se mantenga < 150 (**R10**) y el costo por ejecución mensual sea de apenas ~$0.35 USD.  
  *Pilares Well-Architected:* **Performance Efficiency**, **Cost Optimization**, **Operational Excellence**.

---

### 5.3. Disposición de Datos (Data Layout)
Los datos curados y las métricas se almacenan en **Amazon S3** en formato **Apache Parquet** comprimido con **Snappy**. La tabla de detalle `reservations_curated` se particiona físicamente por la columna `month` (formato `YYYY-MM` derivado de `flight_date`), generando exactamente 24 particiones mensuales (**R4, R5**).

* **¿Por qué Parquet?**  
  Parquet es un formato columnar que almacena metadatos y estadísticas (min/max/conteo) a nivel de encabezado y bloque de columnas. Al consultar una columna específica (ej. `sum(price_cents)`), Athena solo lee los bytes de esa columna en disco, reduciendo el volumen de I/O en más del 80% comparado con CSV.
* **¿Por qué particionar por mes?**  
  Las consultas analíticas y gerenciales se formulan frecuentemente acotadas a un mes de interés (`WHERE month = '2024-05'`). Al particionar por `month`, Athena aplica *Partition Pruning*, omitiendo por completo los directorios de los otros 23 meses.
* **Impacto en bytes escaneados (R6):**  
  Sin particionamiento ni Parquet, una consulta mensual en Athena sobre 2 millones de filas escanearía la totalidad del dataset CSV (~80 MB a 150 MB por consulta). Con Parquet particionado, la consulta escanea únicamente la partición requerida (~1 MB a 2 MB), cumpliendo estrictamente con el umbral de **R6** (bytes escaneados $\le 2 \times$ el tamaño promedio de partición) y reduciendo el costo por consulta en más del 98%.  
  *Pilares Well-Architected:* **Cost Optimization**, **Performance Efficiency**, **Sustainability**.

---

### 5.4. Cómo Obtiene los Números el Panel Gerencial
El panel gerencial expone el endpoint `GET /analytics/occupancy?route=AAA-BBB&month=YYYY-MM`. Cuando un gerente ingresa al panel (`/manager`) y solicita los datos de una ruta y mes, el backend consulta dinámicamente la tabla `route_month_metrics` en **Amazon Athena** mediante el SDK `boto3` (**R7, R9**).

* **Consecuencias en latencia y costo:**  
  Athena responde en aproximadamente 1 a 3 segundos para una tabla agregada en Parquet, cumpliendo con creces el SLA máximo de 10 segundos establecido en **R7**. El costo por query es infinitesimal (< $0.0001 USD), ya que la tabla de métricas ocupa menos de 1 MB.
* **¿Se justifica una caché?**  
  En un entorno de producción donde miles de directores consultan la misma ruta y mes simultáneamente, una capa de caché (ej. Redis en Amazon ElastiCache o caché en memoria en la instancia) estaría completamente justificada para reducir latencias a < 5 ms y evitar consultas repetidas a Athena. Sin embargo, en el alcance del proyecto y según la regla de **R7**, el primer llamado para cada par (ruta, mes) debe consultar Athena obligatoriamente para verificar frescura y permitir que el harness audite el historial de ejecuciones de Athena.  
  *Pilares Well-Architected:* **Performance Efficiency**, **Operational Excellence**.

---

### 5.5. Separación de Cargas de Trabajo (Separation of Workloads)
Uno de los requerimientos de negocio más críticos del escenario es que **las consultas analíticas jamás deben degradar o ralentizar las reservas de los clientes** (**R1, R2**).

* **Aislamiento Físico y de Cómputo:**  
  La base de datos transaccional (OLTP en Amazon RDS PostgreSQL) maneja exclusivamente las operaciones de escritura rápida, consultas de disponibilidad inmediata y bloqueo de asientos atómico.  
  La capa analítica (OLAP) está completamente desacoplada: los datos históricos residen en Amazon S3, el procesamiento batch masivo se ejecuta en un clúster EMR independiente, y las consultas gerenciales se ejecutan sobre la infraestructura serverless de Amazon Athena.
* **Cero Impacto en el Sistema de Venta:**  
  Incluso si un gerente ejecuta consultas analíticas pesadas o se procesan los 2 millones de registros en EMR, el CPU y la memoria de la base de datos PostgreSQL permanecen al 100% disponibles para los pasajeros, asegurando p95 < 1.0 s y cero sobreventa.  
  *Pilares Well-Architected:* **Reliability**, **Performance Efficiency**, **Security**.

---

### 5.6. Tabla de Justificación de Servicios AWS

| Servicio AWS | Alternativa Considerada | Requerimiento Soportado | Pilar(es) Well-Architected |
| :--- | :--- | :--- | :--- |
| **Amazon RDS (PostgreSQL)** | PostgreSQL autogestionado en EC2 | R1, R2, R3, R11 | **Reliability & Operational Excellence**: Parches y backups automatizados, alta integridad relacional. |
| **Amazon EC2 (t3.small)** | AWS Lambda / ECS Fargate | R1, R2, R8, R9, R11 | **Cost Optimization & Performance**: Instancia fija de bajo costo que evita arranques en frío y aloja backend y frontend juntos. |
| **AWS EMR (PySpark en m4.large)** | AWS Glue Studio / Athena CTAS | R4, R10, R11 | **Performance Efficiency & Cost Optimization**: Cómputo distribuido transitorio con `--auto-terminate` que cumple R10. |
| **Amazon S3** | Amazon EFS / HDFS persistente | R4, R5, R6, R11 | **Cost Optimization & Durability**: Almacenamiento desacoplado para el Data Lake con durabilidad 99.999999999%. |
| **AWS Glue Data Catalog** | Catálogo Hive manual en EC2 | R5, R6, R7 | **Operational Excellence**: Metadatos centralizados para Athena y EMR sin gestionar servidores. |
| **Amazon Athena** | Amazon Redshift Serverless | R6, R7, R9 | **Cost Optimization**: Consultas serverless de pago por uso (solo $5 por TB escaneado), ideal para panel gerencial. |

---

### 5.7. Proyección de Costos y Escalabilidad a 10x

```yaml
assumptions: "1000 active users, 5000 bookings/day, 2M reservation records (approx 80MB raw CSV, 25MB curated Parquet in 24 monthly partitions)"
line_items:
  - {service: "RDS", detail: "db.t3.micro, 20 GB gp2, single-AZ", monthly_usd: 14.50}
  - {service: "EC2", detail: "t3.small backend and frontend SPA in single instance", monthly_usd: 15.18}
  - {service: "S3", detail: "Standard storage 5 GB + API GET/PUT requests", monthly_usd: 0.25}
  - {service: "Athena", detail: "Managerial queries (~5 GB scanned/month)", monthly_usd: 0.05}
  - {service: "EMR", detail: "1 monthly batch run, 3 x m4.large, 0.5 h", monthly_usd: 0.35}
  - {service: "Glue", detail: "Data Catalog metadata storage (< 1M objects)", monthly_usd: 0.00}
```
*Total Proyectado:* **~$30.33 USD/mes** (Cumple estrictamente con el techo de $50 USD de **R12**).

#### Análisis de Escalabilidad a 10x (Volumen de Datos o Consultas x10):
1. **Pilar de Cost Optimization:**
   - Si el volumen de datos pasa de 2M a 20M registros (~800 MB raw, ~250 MB Parquet): el costo de almacenamiento en S3 aumenta menos de $0.05 USD/mes.
   - El tiempo de ejecución en EMR subiría de 15 minutos a ~35 minutos en los mismos 3 nodos, incrementando el costo del batch a ~$0.80 USD/mes.
   - Si las consultas de los gerentes se multiplican por 10, Athena escanearía ~50 GB al mes, costando solo $0.25 USD/mes.
   - RDS y EC2 se mantendrían estables en el mismo tipo de instancia gracias a los índices optimizados y la actualización atómica. Costo total estimado a 10x: **~$31.50 USD/mes** (sigue por debajo de los $50 USD).
2. **Pilar de Sustainability (Sostenibilidad):**
   - El uso de almacenamiento columnar Parquet con compresión Snappy reduce en un 70% los ciclos de CPU y transferencias de red necesarias para leer los datos.
   - Al implementar *Partition Pruning*, se evita el procesamiento innecesario de 23 de cada 24 particiones, reduciendo al mínimo la huella de carbono asociada al cómputo en la nube.

