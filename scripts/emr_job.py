#!/usr/bin/env python3
"""
PySpark Batch ETL Job para AWS EMR
Aplica reglas C1-C5 de limpieza y genera:
1. reservations_curated (Parquet, particionado por month=YYYY-MM, 24 particiones)
2. route_month_metrics (Parquet, agregación de métricas de ocupación, ingresos y cancelaciones)
"""
import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, regexp_replace, upper, trim, substring, when, sum, count, coalesce, lit
)

def main():
    if len(sys.argv) < 3:
        print("Uso: spark-submit emr_job.py <s3_or_local_raw_path> <s3_or_local_output_path>")
        sys.exit(1)

    raw_path = sys.argv[1].rstrip("/")
    output_path = sys.argv[2].rstrip("/")

    spark = SparkSession.builder \
        .appName("AirlineBatchProcessing-EMR") \
        .getOrCreate()

    # Configurar para optimizar escritura en Parquet
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")

    # 1. Cargar datos crudos
    flights_csv = f"{raw_path}/flights.csv"
    res_csv = f"{raw_path}/reservations.csv"

    raw_flights = spark.read.option("header", "true").csv(flights_csv)
    raw_res = spark.read.option("header", "true").csv(res_csv)

    # -------------------------------------------------------------
    # Regla C1: ruta en mayúsculas y sin espacios
    # Extraer el mes del vuelo (YYYY-MM)
    # -------------------------------------------------------------
    flights_clean = raw_flights.withColumn(
        "route", upper(regexp_replace(col("route"), r"\s+", ""))
    ).withColumn(
        "capacity", col("capacity").cast("bigint")
    ).withColumn(
        "month", substring(col("flight_date"), 1, 7)
    )

    # -------------------------------------------------------------
    # Reglas de limpieza sobre reservas:
    # C2: status sin espacios y en mayúsculas
    # C3: mantener solo CONFIRMED y CANCELLED
    # C4: eliminar price_cents missing o <= 0
    # C5: eliminar duplicados de reservation_id manteniendo la primera ocurrencia
    # -------------------------------------------------------------
    res_filtered = raw_res.withColumn(
        "status", upper(trim(col("status")))
    ).filter(
        col("status").isin("CONFIRMED", "CANCELLED")
    ).withColumn(
        "price_cents", col("price_cents").cast("bigint")
    ).filter(
        col("price_cents").isNotNull() & (col("price_cents") > 0)
    ).dropDuplicates(["reservation_id"])

    # -------------------------------------------------------------
    # Tabla 1: reservations_curated
    # Columnas en orden estricto: reservation_id, flight_id, route, fare_class, price_cents, status; month
    # -------------------------------------------------------------
    curated = res_filtered.join(
        flights_clean.select("flight_id", "route", "month"),
        on="flight_id",
        how="inner"
    ).select(
        col("reservation_id").cast("string"),
        col("flight_id").cast("string"),
        col("route").cast("string"),
        col("fare_class").cast("string"),
        col("price_cents").cast("bigint"),
        col("status").cast("string"),
        col("month").cast("string")
    )

    curated_target = f"{output_path}/reservations_curated"
    curated.repartition("month").write \
        .mode("overwrite") \
        .partitionBy("month") \
        .parquet(curated_target)
    print(f"Escrito reservations_curated en {curated_target}")

    # -------------------------------------------------------------
    # Tabla 2: route_month_metrics
    # route, month, seats_capacity, seats_sold, occupancy, revenue_cents, bookings, cancellations
    # -------------------------------------------------------------
    cap_df = flights_clean.groupBy("route", "month").agg(
        sum("capacity").alias("seats_capacity")
    )

    res_metrics = curated.groupBy("route", "month").agg(
        sum(when(col("status") == "CONFIRMED", 1).otherwise(0)).cast("bigint").alias("seats_sold"),
        sum(when(col("status") == "CONFIRMED", col("price_cents")).otherwise(0)).cast("bigint").alias("revenue_cents"),
        count(lit(1)).cast("bigint").alias("bookings"),
        sum(when(col("status") == "CANCELLED", 1).otherwise(0)).cast("bigint").alias("cancellations")
    )

    metrics = cap_df.join(
        res_metrics,
        on=["route", "month"],
        how="left"
    ).select(
        col("route").cast("string"),
        col("month").cast("string"),
        coalesce(col("seats_capacity"), lit(0)).cast("bigint").alias("seats_capacity"),
        coalesce(col("seats_sold"), lit(0)).cast("bigint").alias("seats_sold"),
        (coalesce(col("seats_sold"), lit(0)).cast("double") / col("seats_capacity").cast("double")).alias("occupancy"),
        coalesce(col("revenue_cents"), lit(0)).cast("bigint").alias("revenue_cents"),
        coalesce(col("bookings"), lit(0)).cast("bigint").alias("bookings"),
        coalesce(col("cancellations"), lit(0)).cast("bigint").alias("cancellations")
    )

    metrics_target = f"{output_path}/route_month_metrics"
    metrics.coalesce(1).write \
        .mode("overwrite") \
        .parquet(metrics_target)
    print(f"Escrito route_month_metrics en {metrics_target}")

    spark.stop()

if __name__ == "__main__":
    main()

