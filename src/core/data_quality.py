"""Quality gates integrados para el contrato canónico.

Estas validaciones se ejecutan después del mapping/casteo de cada dominio y
antes de que los datos lleguen a feature engineering o modelos.

Objetivos:
- impedir claves vacías o duplicadas;
- rechazar montos contractuales negativos;
- comprobar integridad referencial cuando ambas tablas están configuradas;
- producir evidencia machine-readable sin materializar datasets Spark en pandas.
"""

from __future__ import annotations

from typing import Any


PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "contracts": ("id_contrato",),
    "suppliers": ("id_proveedor",),
    "entities": ("id_entidad",),
    "officials": ("id_funcionario",),
    "payments": ("id_pago",),
}

# child_domain, child_field, parent_domain, parent_field
FOREIGN_KEYS: tuple[tuple[str, str, str, str], ...] = (
    ("contracts", "id_proveedor", "suppliers", "id_proveedor"),
    ("contracts", "id_entidad", "entities", "id_entidad"),
    ("contracts", "id_funcionario", "officials", "id_funcionario"),
    ("payments", "id_contrato", "contracts", "id_contrato"),
)

ID_FIELDS = {
    "id_contrato",
    "id_proveedor",
    "id_entidad",
    "id_funcionario",
    "id_pago",
}


def validar_calidad_integrada_pandas(datasets: dict[str, Any]) -> dict[str, Any]:
    """Valida calidad relacional para DataFrames pandas.

    Las relaciones cuyo dominio padre no fue configurado se registran como
    ``skipped_parent_not_configured``; esto permite TRAIN mínimo con solo
    ``contracts`` sin fingir una validación que no pudo realizarse.
    """
    summary: dict[str, Any] = {
        "status": "ok",
        "engine": "pandas",
        "domains": {},
        "foreign_keys": {},
    }

    for domain, df in datasets.items():
        key = PRIMARY_KEYS.get(domain)
        if not key:
            continue

        _validar_ids_no_vacios_pandas(df, domain)
        _validar_reglas_dominio_pandas(df, domain)

        missing_key = sorted(set(key) - set(df.columns))
        if missing_key:
            raise ValueError(
                f"Quality gate {domain!r}: faltan columnas de clave primaria {missing_key}"
            )

        duplicate_mask = df.duplicated(subset=list(key), keep=False)
        duplicate_rows = int(duplicate_mask.sum())
        duplicate_keys = int(df.loc[duplicate_mask, list(key)].drop_duplicates().shape[0])
        if duplicate_keys:
            muestra = (
                df.loc[duplicate_mask, list(key)]
                .drop_duplicates()
                .head(5)
                .astype("string")
                .to_dict("records")
            )
            raise ValueError(
                f"Quality gate {domain!r}: {duplicate_keys} claves duplicadas "
                f"({duplicate_rows} filas afectadas); muestra={muestra}"
            )

        summary["domains"][domain] = {
            "rows": int(len(df)),
            "primary_key": list(key),
            "duplicate_keys": 0,
            "duplicate_rows": 0,
            "blank_identifiers": 0,
        }

    for child_domain, child_field, parent_domain, parent_field in FOREIGN_KEYS:
        relation_id = f"{child_domain}.{child_field}->{parent_domain}.{parent_field}"
        if child_domain not in datasets:
            continue
        if parent_domain not in datasets:
            summary["foreign_keys"][relation_id] = {
                "status": "skipped_parent_not_configured",
                "orphans": None,
            }
            continue

        child = datasets[child_domain]
        parent = datasets[parent_domain]
        if child_field not in child.columns or parent_field not in parent.columns:
            raise ValueError(
                f"Quality gate referencial {relation_id}: columnas requeridas no disponibles."
            )

        child_values = child.loc[child[child_field].notna(), child_field].astype("string").drop_duplicates()
        parent_values = set(parent.loc[parent[parent_field].notna(), parent_field].astype("string"))
        orphan_values = child_values.loc[~child_values.isin(parent_values)]
        orphan_count = int(len(orphan_values))
        if orphan_count:
            muestra = orphan_values.head(5).tolist()
            raise ValueError(
                f"Quality gate referencial {relation_id}: {orphan_count} claves huérfanas; "
                f"muestra={muestra}"
            )
        summary["foreign_keys"][relation_id] = {"status": "ok", "orphans": 0}

    return summary


def validar_calidad_integrada_spark(datasets: dict[str, Any]) -> dict[str, Any]:
    """Equivalente distribuido para DataFrames Spark.

    Ejecuta agregaciones/anti-joins Spark y solo colecta escalares o una muestra
    de claves cuando existe un error. El dataset contractual nunca se convierte
    a pandas ni se colecta completo al driver.
    """
    from pyspark.sql import functions as F

    summary: dict[str, Any] = {
        "status": "ok",
        "engine": "spark",
        "domains": {},
        "foreign_keys": {},
    }

    for domain, df in datasets.items():
        key = PRIMARY_KEYS.get(domain)
        if not key:
            continue
        missing_key = sorted(set(key) - set(df.columns))
        if missing_key:
            raise ValueError(
                f"Quality gate {domain!r}: faltan columnas de clave primaria {missing_key}"
            )

        id_columns = sorted(ID_FIELDS & set(df.columns))
        aggregations = [
            F.count(F.lit(1)).alias("__rows"),
            F.countDistinct(*[F.col(c) for c in key]).alias("__distinct_pk"),
        ]
        for column in id_columns:
            aggregations.append(
                F.sum(
                    F.when(
                        F.col(column).isNotNull()
                        & (F.length(F.trim(F.col(column).cast("string"))) == 0),
                        1,
                    ).otherwise(0)
                ).alias(f"__blank__{column}")
            )
        if domain == "contracts" and "monto" in df.columns:
            aggregations.append(
                F.sum(
                    F.when(F.col("monto").isNotNull() & (F.col("monto") < 0), 1).otherwise(0)
                ).alias("__negative_monto")
            )

        metrics = df.agg(*aggregations).first().asDict()
        rows = int(metrics.get("__rows") or 0)
        distinct_pk = int(metrics.get("__distinct_pk") or 0)
        duplicate_excess_rows = rows - distinct_pk
        blank_identifiers = {
            c: int(metrics.get(f"__blank__{c}") or 0)
            for c in id_columns
            if int(metrics.get(f"__blank__{c}") or 0) > 0
        }
        if blank_identifiers:
            raise ValueError(
                f"Quality gate {domain!r}: identificadores vacíos/no válidos {blank_identifiers}"
            )
        if int(metrics.get("__negative_monto") or 0) > 0:
            raise ValueError(
                f"Quality gate 'contracts': {int(metrics['__negative_monto'])} montos negativos"
            )
        if duplicate_excess_rows > 0:
            duplicate_groups = (
                df.groupBy(*[F.col(c) for c in key])
                .count()
                .where(F.col("count") > 1)
            )
            duplicate_keys = int(duplicate_groups.count())
            muestra = [row.asDict() for row in duplicate_groups.limit(5).collect()]
            raise ValueError(
                f"Quality gate {domain!r}: {duplicate_keys} claves duplicadas "
                f"({duplicate_excess_rows} filas excedentes); muestra={muestra}"
            )

        summary["domains"][domain] = {
            "rows": rows,
            "primary_key": list(key),
            "duplicate_keys": 0,
            "duplicate_excess_rows": 0,
            "blank_identifiers": 0,
        }

    for child_domain, child_field, parent_domain, parent_field in FOREIGN_KEYS:
        relation_id = f"{child_domain}.{child_field}->{parent_domain}.{parent_field}"
        if child_domain not in datasets:
            continue
        if parent_domain not in datasets:
            summary["foreign_keys"][relation_id] = {
                "status": "skipped_parent_not_configured",
                "orphans": None,
            }
            continue

        child = datasets[child_domain]
        parent = datasets[parent_domain]
        if child_field not in child.columns or parent_field not in parent.columns:
            raise ValueError(
                f"Quality gate referencial {relation_id}: columnas requeridas no disponibles."
            )

        child_keys = (
            child.where(F.col(child_field).isNotNull())
            .select(F.col(child_field).cast("string").alias("__fk"))
            .distinct()
        )
        parent_keys = (
            parent.where(F.col(parent_field).isNotNull())
            .select(F.col(parent_field).cast("string").alias("__pk"))
            .distinct()
        )
        orphans = child_keys.join(parent_keys, child_keys["__fk"] == parent_keys["__pk"], "left_anti")
        orphan_count = int(orphans.count())
        if orphan_count:
            muestra = [row["__fk"] for row in orphans.limit(5).collect()]
            raise ValueError(
                f"Quality gate referencial {relation_id}: {orphan_count} claves huérfanas; "
                f"muestra={muestra}"
            )
        summary["foreign_keys"][relation_id] = {"status": "ok", "orphans": 0}

    return summary


def _validar_ids_no_vacios_pandas(df, domain: str) -> None:
    for column in sorted(ID_FIELDS & set(df.columns)):
        values = df[column].astype("string")
        blank = values.notna() & values.str.strip().eq("")
        n_blank = int(blank.fillna(False).sum())
        if n_blank:
            raise ValueError(
                f"Quality gate {domain!r}: {column} contiene {n_blank} identificadores vacíos"
            )


def _validar_reglas_dominio_pandas(df, domain: str) -> None:
    if domain == "contracts" and "monto" in df.columns:
        negativos = df["monto"].notna() & (df["monto"] < 0)
        n_negativos = int(negativos.sum())
        if n_negativos:
            raise ValueError(
                f"Quality gate 'contracts': {n_negativos} montos negativos"
            )
