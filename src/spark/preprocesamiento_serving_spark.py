"""TRANSFORM framework-neutral usado por TRAIN/INFERENCE Spark.

El estado se aprende fuera de este módulo y llega como un diccionario/JSON
versionado. Aquí no existe ninguna operación de FIT. CSV/SQL Server pueden usar
``pandas_a_spark`` como adaptador; ``spark_sql`` entra ya como DataFrame Spark.
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
