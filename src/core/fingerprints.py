"""Fingerprints deterministas compartidos por evaluación y TRAIN.

No son una función de anonimización ni seguridad; sirven para ligar evidencia de
validación, manifest de candidate y corpus de entrenamiento dentro del PoC.
"""

from __future__ import annotations

import hashlib
import json

import pandas as pd
from pyspark.sql import functions as F


def fingerprint_pandas_dataframe(df: pd.DataFrame) -> str:
    normalized = df.copy()
    for col in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[col]):
            normalized[col] = normalized[col].dt.strftime("%Y-%m-%dT%H:%M:%S")
    return hashlib.sha256(
        normalized.to_csv(index=False, na_rep="<NA>").encode("utf-8")
    ).hexdigest()


def fingerprint_spark_dataframe(df) -> str:
    """Fingerprint agregado distribuido sin colectar las filas al driver."""
    columns = sorted(df.columns)
    values = [F.coalesce(F.col(c).cast("string"), F.lit("<NA>")) for c in columns]
    hashed = df.select(
        F.xxhash64(*values).alias("_h1"),
        F.xxhash64(F.lit("cgr-spark-native-v1"), *values).alias("_h2"),
    )
    stats = hashed.agg(
        F.count(F.lit(1)).alias("rows"),
        F.sum(F.col("_h1").cast("decimal(38,0)")).cast("string").alias("sum_h1"),
        F.sum(F.col("_h2").cast("decimal(38,0)")).cast("string").alias("sum_h2"),
        F.min("_h1").alias("min_h1"),
        F.max("_h1").alias("max_h1"),
        F.min("_h2").alias("min_h2"),
        F.max("_h2").alias("max_h2"),
    ).first().asDict()
    payload = {
        "columns": columns,
        "schema": df.schema.jsonValue(),
        "stats": {k: (None if v is None else str(v)) for k, v in stats.items()},
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
