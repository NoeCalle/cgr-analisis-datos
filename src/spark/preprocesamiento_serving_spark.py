"""Preprocesamiento compartido por TRAIN/INFERENCE Spark.

Para fuentes pandas, el estado puede seguir aprendién-dose con el módulo legacy
corregido y luego transformarse aquí. Para ``spark_sql``, Sprint 5 incorpora FIT
Spark-native: el dataset completo nunca se materializa en pandas.
"""

from __future__ import annotations

import pandas as pd
from pyspark.sql import functions as F

PREPROCESSOR_SCHEMA_VERSION = 1


def pandas_a_spark(spark, df: pd.DataFrame):
    """Adaptador de compatibilidad para CSV/SQL Server; no se usa con spark_sql."""
    serializable = df.copy()
    for col in serializable.columns:
        if pd.api.types.is_datetime64_any_dtype(serializable[col]):
            serializable[col] = serializable[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    serializable = serializable.astype(object).where(pd.notna(serializable), None)
    return spark.createDataFrame(serializable.to_dict("records"))


def ajustar_estado_preprocesamiento_spark(df: object) -> dict:
    """Aprende el estado de imputación sobre un DataFrame Spark.

    Usa ``percentile_approx`` para cuantiles escalables. Solo se colecta al driver
    la tabla agregada ``objeto -> mediana`` que forma parte del artefacto de
    preprocesamiento; las filas contractuales nunca se colectan.
    """
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
    global_values = partial.where(F.col("_monto_parcial").isNotNull())
    global_row = global_values.agg(
        F.percentile_approx("_monto_parcial", 0.5, 10000).alias("mediana")
    ).first()
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

    medians_rows = medians_df.collect()
    medianas_objeto = {
        str(row["_objeto_fit"]): float(row["_mediana_objeto"])
        for row in medians_rows
        if row["_objeto_fit"] is not None and row["_mediana_objeto"] is not None
    }

    return {
        "schema_version": PREPROCESSOR_SCHEMA_VERSION,
        "fit_engine": "spark",
        "quantile_method": "percentile_approx_accuracy_10000",
        "monto_mediana_por_objeto": medianas_objeto,
        "monto_mediana_global": mediana_global,
        "modalidad_moda": str(modalidad_moda),
        "objeto_moda": str(objeto_moda),
        "monto_p99": p99,
        "object_medians_count": len(medianas_objeto),
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


def aplicar_preprocesamiento_congelado(df, estado: dict):
    """TRANSFORM Spark usando exclusivamente parámetros previamente aprendidos."""
    if estado.get("schema_version") != PREPROCESSOR_SCHEMA_VERSION:
        raise ValueError(
            f"Preprocesador JSON incompatible: schema_version={estado.get('schema_version')!r}"
        )

    medianas = estado.get("monto_mediana_por_objeto", {})
    if medianas:
        entries = []
        for key, value in sorted(medianas.items()):
            entries.extend([F.lit(str(key)), F.lit(float(value))])
        mapa_mediana = F.create_map(*entries)
        mediana_objeto = mapa_mediana[F.col("objeto").cast("string")]
    else:
        mediana_objeto = F.lit(None).cast("double")

    # El monto observado tiene prioridad. Un objeto nulo nunca puede borrar un
    # monto válido, corrección explícita respecto de la ruta legacy de RC1.
    out = df.withColumn(
        "monto",
        F.coalesce(
            F.col("monto").cast("double"),
            mediana_objeto,
            F.lit(float(estado["monto_mediana_global"])),
        ),
    )
    out = out.withColumn(
        "modalidad",
        F.coalesce(F.col("modalidad").cast("string"), F.lit(str(estado["modalidad_moda"]))),
    )
    out = out.withColumn(
        "objeto",
        F.coalesce(F.col("objeto").cast("string"), F.lit(str(estado["objeto_moda"]))),
    )
    out = out.withColumn(
        "monto_capped",
        F.least(F.col("monto"), F.lit(float(estado["monto_p99"]))),
    )
    if "id_funcionario" not in out.columns:
        out = out.withColumn("id_funcionario", F.lit("__NO_DISPONIBLE__"))
    else:
        out = out.withColumn(
            "id_funcionario",
            F.coalesce(F.col("id_funcionario").cast("string"), F.lit("__NO_DISPONIBLE__")),
        )
    out = out.withColumn(
        "es_contratacion_directa", F.col("modalidad") == F.lit("Contratación Directa")
    )
    out = out.withColumn(
        "es_comparacion_precios", F.col("modalidad") == F.lit("Comparación de Precios")
    )
    return out
