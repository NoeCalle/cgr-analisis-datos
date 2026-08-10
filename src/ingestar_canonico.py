"""Ingesta configurable hacia el contrato canónico del módulo.

Rutas de ejecución:
- ``local_csv`` / ``sqlserver`` -> pandas;
- ``spark_sql`` -> DataFrame Spark nativo, sin ``toPandas()``.

Uso:
    python src/ingestar_canonico.py --config config/local.yaml
    python src/ingestar_canonico.py --config config/cgr.example.yaml --validate-only
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from connectors import crear_connector
from core.config import cargar_config, obtener_version_contrato
from core.data_quality import (
    validar_calidad_integrada_pandas,
    validar_calidad_integrada_spark,
)
from core.schemas import aplicar_mapping, validar_dataframe


def integrar_dominio(config, connector, domain):
    """Integra un dominio pandas. No acepta spark_sql para evitar collect implícito."""
    if config["source"]["type"] == "spark_sql":
        raise ValueError("spark_sql requiere integrar_spark(); no se materializa implícitamente en pandas.")
    mapping = config["mapping"][domain]
    physical_columns = list(dict.fromkeys(mapping.values()))
    raw = connector.read(domain, physical_columns)
    canonical = aplicar_mapping(raw, domain, mapping)
    return validar_dataframe(canonical, domain, config.get("mode", "inference"))


def integrar(config, output_dir=None):
    """Integración pandas para CSV/SQL Server con quality gates relacionales."""
    if config["source"]["type"] == "spark_sql":
        raise ValueError(
            "source.type=spark_sql usa la ruta Spark-native. Llame integrar_spark(config, spark=...)."
        )

    domains = [d for d in config["mapping"] if _domain_available(config, d)]
    results = {}
    summary = _summary_base(config, native_engine="pandas")

    with _managed_connector(crear_connector(config)) as connector:
        for domain in domains:
            df = integrar_dominio(config, connector, domain)
            results[domain] = df
            summary["domains"][domain] = {
                "rows": int(len(df)),
                "columns": list(df.columns),
            }

    quality = validar_calidad_integrada_pandas(results)
    summary["quality"] = quality

    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for domain, df in results.items():
            df.to_csv(out / f"{domain}.csv", index=False)
        _write_manifest(out, summary)

    return results, summary


def integrar_spark(config, *, spark, output_dir=None):
    """Integración canónica Spark-native para ``source.type=spark_sql``.

    Mantiene DataFrames Spark durante lectura, mapping, casteo y validación.
    Los quality gates realizan agregaciones/anti-joins distribuidos y solo
    colectan métricas escalares; nunca colectan el dataset contractual.
    """
    if config["source"]["type"] != "spark_sql":
        raise ValueError("integrar_spark() está reservado a source.type=spark_sql.")

    from core.schemas_spark import aplicar_mapping_spark, validar_dataframe_spark

    domains = [d for d in config["mapping"] if _domain_available(config, d)]
    results = {}
    summary = _summary_base(config, native_engine="spark")

    with _managed_connector(crear_connector(config, spark=spark)) as connector:
        for domain in domains:
            mapping = config["mapping"][domain]
            physical_columns = list(dict.fromkeys(mapping.values()))
            raw = connector.read(domain, physical_columns)
            canonical = aplicar_mapping_spark(raw, domain, mapping)
            canonical = validar_dataframe_spark(
                canonical, domain, config.get("mode", "inference")
            )
            results[domain] = canonical
            summary["domains"][domain] = {
                # El conteo se obtiene junto con la validación de unicidad para
                # evitar el count() completo que antes se ejecutaba aquí.
                "rows": None,
                "columns": list(canonical.columns),
            }

    quality = validar_calidad_integrada_spark(results)
    summary["quality"] = quality
    for domain, domain_quality in quality["domains"].items():
        if domain in summary["domains"]:
            summary["domains"][domain]["rows"] = int(domain_quality["rows"])

    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for domain, df in results.items():
            target = out / domain
            df.write.mode("overwrite").option("header", True).csv(str(target))
        _write_manifest(out, summary)

    return results, summary


def _summary_base(config, *, native_engine: str):
    return {
        "schema_version": 3,
        "contract_schema_version": obtener_version_contrato(config),
        "mode": config.get("mode", "inference"),
        "source_type": config["source"]["type"],
        "native_engine": native_engine,
        "domains": {},
        "contains_secrets": False,
    }


def _write_manifest(out: Path, summary: dict) -> None:
    (out / "integration_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _domain_available(config, domain):
    source = config["source"]
    locations = source.get("datasets", {}) if source["type"] == "local_csv" else source.get("tables", {})
    return domain in locations


class _managed_connector:
    def __init__(self, connector):
        self.connector = connector

    def __enter__(self):
        return self.connector

    def __exit__(self, exc_type, exc, tb):
        self.connector.close()
        return False


def main():
    parser = argparse.ArgumentParser(description="Valida una fuente contra el esquema canónico CGR PoC.")
    parser.add_argument("--config", required=True, help="Ruta YAML de configuración.")
    parser.add_argument(
        "--output-dir",
        default="outputs/integracion_canonica",
        help="Directorio de preview canónico (solo datos no sensibles/locales).",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Valida configuración sin conectarse ni escribir datos.",
    )
    args = parser.parse_args()

    config = cargar_config(args.config)
    if args.validate_only:
        print(
            f"CONFIG OK | contract_schema=v{obtener_version_contrato(config)} | "
            f"mode={config.get('mode', 'inference')} | "
            f"source={config['source']['type']} | domains={sorted(config['mapping'])}"
        )
        return

    if config["source"]["type"] == "spark_sql":
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.appName("cgr-integracion-canonica").getOrCreate()
        try:
            _, summary = integrar_spark(config, spark=spark, output_dir=args.output_dir)
        finally:
            spark.stop()
    else:
        _, summary = integrar(config, output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
