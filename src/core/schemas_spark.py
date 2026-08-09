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

    # select(alias) descarta deliberadamente columnas no mapeadas.
    return df.select(*[F.col(physical).alias(canonical) for canonical, physical in mapping.items()])


def validar_dataframe_spark(df, domain: str, mode: str = "inference"):
    """Valida/castea un DataFrame Spark sin convertirlo a pandas.

    La validación ejecuta una sola agregación distribuida para contabilizar
    conversiones inválidas y nulos estructurales. No imputa calidad de negocio.
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
    invalid_checks = []
    null_checks = []

    for col in df.columns:
        spec = specs[col]
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

        if spec.kind in {"number", "datetime", "boolean"}:
            invalid_checks.append(
                F.sum(F.when(original.isNotNull() & converted.isNull(), 1).otherwise(0)).alias(
                    f"invalid__{col}"
                )
            )
        out = out.withColumn(col, converted)

        required_here = spec.required_training if mode == "training" else spec.required_inference
        if required_here and not spec.nullable:
            null_checks.append(
                F.sum(F.when(F.col(col).isNull(), 1).otherwise(0)).alias(f"null__{col}")
            )

    checks = invalid_checks + null_checks
    if checks:
        result = out.agg(*checks).collect()[0].asDict()
        invalid = {
            key.removeprefix("invalid__"): int(value or 0)
            for key, value in result.items()
            if key.startswith("invalid__") and int(value or 0) > 0
        }
        if invalid:
            raise ValueError(
                f"Conversiones inválidas en esquema Spark {domain!r}: {invalid}"
            )
        structural_nulls = {
            key.removeprefix("null__"): int(value or 0)
            for key, value in result.items()
            if key.startswith("null__") and int(value or 0) > 0
        }
        if structural_nulls:
            raise ValueError(
                f"Nulos no permitidos en esquema Spark {domain!r} ({mode}): {structural_nulls}"
            )

    return out
