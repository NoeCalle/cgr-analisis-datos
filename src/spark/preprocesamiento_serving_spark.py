"""TRANSFORM framework-neutral usado por TRAIN/INFERENCE Spark.

El estado se aprende fuera de este módulo y llega como JSON. Para champions
Spark-native, las medianas por objeto pueden llegar además como DataFrame Spark
y se aplican mediante join distribuido. Aquí no existe ninguna operación de FIT.
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


def aplicar_preprocesamiento_congelado(df, estado: dict, *, medianas_df=None):
    """TRANSFORM Spark usando exclusivamente parámetros previamente aprendidos."""
    if estado.get("schema_version") != PREPROCESSOR_SCHEMA_VERSION:
        raise ValueError(
            f"Preprocesador JSON incompatible: schema_version={estado.get('schema_version')!r}"
        )

    out = df
    external = bool(estado.get("monto_mediana_por_objeto_external", False))
    if external:
        if medianas_df is None:
            raise ValueError(
                "El preprocesador requiere artefacto Spark de medianas por objeto y no fue suministrado."
            )
        requeridas = {"objeto", "monto_mediana"}
        faltantes = sorted(requeridas - set(medianas_df.columns))
        if faltantes:
            raise ValueError(f"Artefacto de medianas Spark incompleto: faltan {faltantes}")
        med = medianas_df.select(
            F.col("objeto").cast("string").alias("__objeto_mediana"),
            F.col("monto_mediana").cast("double").alias("__mediana_objeto"),
        )
        out = out.join(
            med,
            out["objeto"].cast("string") == med["__objeto_mediana"],
            "left",
        ).drop("__objeto_mediana")
        mediana_objeto = F.col("__mediana_objeto")
    else:
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
    out = out.withColumn(
        "monto",
        F.coalesce(
            F.col("monto").cast("double"),
            mediana_objeto,
            F.lit(float(estado["monto_mediana_global"])),
        ),
    )
    if "__mediana_objeto" in out.columns:
        out = out.drop("__mediana_objeto")

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
