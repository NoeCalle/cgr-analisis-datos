"""FIT distribuido del preprocesador para TRAIN con ``source.type=spark_sql``.

Aprende medianas, modas y P99 sin materializar filas contractuales en pandas.
Cuando se suministra ``medians_output_path``, la dimensión objeto->mediana se
persiste como Parquet Spark y tampoco se colecta al driver.
"""

from __future__ import annotations

from pathlib import Path

from pyspark.sql import functions as F

PREPROCESSOR_SCHEMA_VERSION = 1


def ajustar_estado_preprocesamiento_spark(df, *, medians_output_path: str | Path | None = None) -> dict:
    requeridas = {"monto", "objeto", "modalidad"}
    faltantes = sorted(requeridas - set(df.columns))
    if faltantes:
        raise ValueError(f"FIT Spark requiere columnas de preprocesamiento: {faltantes}")

    base = (
        df.withColumn("_monto_fit", F.col("monto").cast("double"))
        .withColumn("_objeto_fit", F.col("objeto").cast("string"))
    )

    medians_df = (
        base.where(F.col("_objeto_fit").isNotNull() & F.col("_monto_fit").isNotNull())
        .groupBy("_objeto_fit")
        .agg(F.percentile_approx("_monto_fit", 0.5, 10000).alias("_mediana_objeto"))
    )

    partial = (
        base.join(medians_df, on="_objeto_fit", how="left")
        .withColumn("_monto_parcial", F.coalesce(F.col("_monto_fit"), F.col("_mediana_objeto")))
    )
    global_row = (
        partial.where(F.col("_monto_parcial").isNotNull())
        .agg(F.percentile_approx("_monto_parcial", 0.5, 10000).alias("mediana"))
        .first()
    )
    if global_row is None or global_row["mediana"] is None:
        raise ValueError("No se puede ajustar preprocesamiento Spark: monto no tiene valores válidos.")
    mediana_global = float(global_row["mediana"])

    imputed = partial.withColumn(
        "_monto_imputado", F.coalesce(F.col("_monto_parcial"), F.lit(mediana_global))
    )
    p99_row = imputed.agg(
        F.percentile_approx("_monto_imputado", 0.99, 10000).alias("p99")
    ).first()
    p99 = float(p99_row["p99"])

    modalidad_moda = _moda_spark(base, "modalidad")
    objeto_moda = _moda_spark(base, "objeto")
    n_medians = int(medians_df.count())

    if medians_output_path is not None:
        medians_path = Path(medians_output_path)
        (
            medians_df.select(
                F.col("_objeto_fit").alias("objeto"),
                F.col("_mediana_objeto").cast("double").alias("monto_mediana"),
            )
            .write.mode("overwrite")
            .parquet(str(medians_path))
        )
        medianas_objeto = {}
        external_medians = True
    else:
        # Solo para pruebas/compatibilidad de lotes pequeños. TRAIN spark_sql
        # productivo debe suministrar medians_output_path.
        medians_rows = medians_df.collect()
        medianas_objeto = {
            str(row["_objeto_fit"]): float(row["_mediana_objeto"])
            for row in medians_rows
            if row["_objeto_fit"] is not None and row["_mediana_objeto"] is not None
        }
        external_medians = False

    return {
        "schema_version": PREPROCESSOR_SCHEMA_VERSION,
        "fit_engine": "spark",
        "quantile_method": "percentile_approx_accuracy_10000",
        "monto_mediana_por_objeto": medianas_objeto,
        "monto_mediana_por_objeto_external": external_medians,
        "monto_mediana_global": mediana_global,
        "modalidad_moda": str(modalidad_moda),
        "objeto_moda": str(objeto_moda),
        "monto_p99": p99,
        "object_medians_count": n_medians,
    }


def _moda_spark(df, campo: str):
    row = (
        df.where(F.col(campo).isNotNull())
        .groupBy(F.col(campo).cast("string").alias("value"))
        .count()
        .orderBy(F.desc("count"), F.asc("value"))
        .first()
    )
    if row is None:
        raise ValueError(f"No se puede ajustar preprocesamiento Spark: {campo} no tiene valores válidos.")
    return row["value"]
