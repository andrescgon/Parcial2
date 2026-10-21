-- ====================================================================
-- Script SQL para Amazon Athena / AWS Glue Data Catalog
-- Requerimiento R5: Contratos de Datos y Registro de Tablas
-- Base de Datos: airline_analytics
-- ====================================================================

CREATE DATABASE IF NOT EXISTS airline_analytics;

-- --------------------------------------------------------------------
-- Tabla 1: reservations_curated
-- Parquet particionado por mes (24 particiones: month=YYYY-MM)
-- --------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS airline_analytics.reservations_curated (
    reservation_id STRING,
    flight_id STRING,
    route STRING,
    fare_class STRING,
    price_cents BIGINT,
    status STRING
)
PARTITIONED BY (month STRING)
STORED AS PARQUET
LOCATION 's3://REEMPLAZAR_CON_TU_BUCKET/curated/reservations_curated/'
TBLPROPERTIES ('parquet.compression'='SNAPPY');

-- Registrar automáticamente las 24 particiones en el Catálogo de Glue:
MSCK REPAIR TABLE airline_analytics.reservations_curated;


-- --------------------------------------------------------------------
-- Tabla 2: route_month_metrics
-- Parquet con métricas agregadas mensuales por ruta
-- --------------------------------------------------------------------
CREATE EXTERNAL TABLE IF NOT EXISTS airline_analytics.route_month_metrics (
    route STRING,
    month STRING,
    seats_capacity BIGINT,
    seats_sold BIGINT,
    occupancy DOUBLE,
    revenue_cents BIGINT,
    bookings BIGINT,
    cancellations BIGINT
)
STORED AS PARQUET
LOCATION 's3://REEMPLAZAR_CON_TU_BUCKET/curated/route_month_metrics/'
TBLPROPERTIES ('parquet.compression'='SNAPPY');

