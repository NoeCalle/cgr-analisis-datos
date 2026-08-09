"""Contrato canónico Spark-native para fuentes distribuidas.

Este módulo refleja las reglas de ``core.schemas`` sin materializar los datos en
pandas. Se usa cuando ``source.type=spark_sql`` para conservar un DataFrame Spark
desde la fuente hasta el preprocesamiento/MLlib.
"""

from __future__ import annotations

from pyspark.sql import functions as F

from core.schemas import SCHEMAS, campos_canonicos, campos_requeridos

_TRUE = {"1", "true", "t", "si", "sí", "yes", "y"}
_FALSE = {"0", "false", "f", "no", "n"}


def aplicar_mapping_spark(df, domain: str, mapping: dict[str, str]):
    if domain not in SCHEMAS:
        raise ValueError(f"Dominio desconocido {domain!r}. Válidos: {sorted(SCHEMAS)}")
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError(f"Mapping vacío o inválido para dominio {domain!r}.")

    canonicos = set(campos_canonicos(domain))
    desconocidos = set(mapping) - canonicos
    if desconocidos:
        raise ValueError(
            f"Campos canónicos desconocidos en mapping {domain!r}: {sorted(desconocidos)}"
        )

    fisicos = list(mapping.values())
    duplicados = sorted({c for c in fisicos if fisicos.count(c) > 1})
    if duplicados:
        raise ValueError(
            f"Una columna física no puede alimentar múltiples campos canónicos: {duplicados}"
        )

    faltantes = sorted(set(fisicos) - set(df.columns))
    if faltantes:
        raise ValueError(
            f"La fuente {domain!r} no contiene columnas configuradas: {faltantes}"
        )

    return df.select(*[F.col(physical).alias(canonical) for canonical, physical in mapping.items()])


def validar_dataframe_spark(df, domain: str, mode: str = "inference"):
    """Valida/castea un DataFrame Spark sin convertirlo a pandas.

    Los marcadores de error se calculan antes de reemplazar cada columna para
    poder distinguir un valor físico inválido de un nulo legítimo.
    """
    if domain not in SCHEMAS:
        raise ValueError(f"Dominio desconocido {domain!r}. Válidos: {sorted(SCHEMAS)}")
    if mode not in {"inference", "training"}:
        raise ValueError("mode debe ser 'inference' o 'training'.")

    required = set(campos_requeridos(domain, mode))
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(
            f"Esquema canónico incompleto para {domain!r} ({mode}): faltan {missing}"
        )

    specs = {field.name: field for field in SCHEMAS[domain]}
    desconocidas = sorted(set(df.columns) - set(specs))
    if desconocidas:
        raise ValueError(f"Columnas no canónicas en {domain!r}: {desconocidas}")

    out = df
    marker_cols: list[str] = []

    for col in df.columns:
        spec = specs[col]
        tmp = f"__converted__{col}"
        invalid_marker = f"__invalid__{col}"
        null_marker = f"__null__{col}"
        original = F.col(col)

        if spec.kind == "string":
            converted = original.cast("string")
        elif spec.kind == "number":
            converted = F.expr(f"try_cast(`{col}` as double)")
        elif spec.kind == "datetime":
            converted = F.expr(f"try_cast(`{col}` as timestamp)")
        elif spec.kind == "boolean":
            normalized = F.lower(F.trim(original.cast("string")))
            converted = (
                F.when(normalized.isin(*sorted(_TRUE)), F.lit(True))
                .when(normalized.isin(*sorted(_FALSE)), F.lit(False))
                .otherwise(F.lit(None).cast("boolean"))
            )
        else:
            raise ValueError(f"Tipo canónico Spark no soportado: {spec.kind!r}")

        out = out.withColumn(tmp, converted)
        if spec.kind in {"number", "datetime", "boolean"}:
            out = out.withColumn(
                invalid_marker,
                F.when(F.col(col).isNotNull() & F.col(tmp).isNull(), 1).otherwise(0),
            )
            marker_cols.append(invalid_marker)

        out = out.drop(col).withColumnRenamed(tmp, col)

        required_here = spec.required_training if mode == "training" else spec.required_inference
        if required_here and not spec.nullable:
            out = out.withColumn(
                null_marker, F.when(F.col(col).isNull(), 1).otherwise(0)
            )
            marker_cols.append(null_marker)

    if marker_cols:
        result = out.agg(*[F.sum(F.col(c)).alias(c) for c in marker_cols]).first().asDict()
        invalid = {
            key.removeprefix("__invalid__"): int(value or 0)
            for key, value in result.items()
            if key.startswith("__invalid__") and int(value or 0) > 0
        }
        if invalid:
            raise ValueError(f"Conversiones inválidas en esquema Spark {domain!r}: {invalid}")

        structural_nulls = {
            key.removeprefix("__null__"): int(value or 0)
            for key, value in result.items()
            if key.startswith("__null__") and int(value or 0) > 0
        }
        if structural_nulls:
            raise ValueError(
                f"Nulos no permitidos en esquema Spark {domain!r} ({mode}): {structural_nulls}"
            )
        out = out.drop(*marker_cols)

    return out
