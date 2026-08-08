"""Ingesta configurable hacia el contrato canónico del módulo.

Sprint 1: prueba el desacoplamiento fuente -> mapping -> esquema canónico sin
alterar todavía los pipelines de entrenamiento/inferencia del PoC.

Uso:
    python src/ingestar_canonico.py --config config/local.yaml
    python src/ingestar_canonico.py --config config/cgr.example.yaml --validate-only
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from connectors import crear_connector
from core.config import cargar_config
from core.schemas import aplicar_mapping, validar_dataframe


def integrar_dominio(config, connector, domain):
    mapping = config["mapping"][domain]
    physical_columns = list(dict.fromkeys(mapping.values()))
    raw = connector.read(domain, physical_columns)
    canonical = aplicar_mapping(raw, domain, mapping)
    return validar_dataframe(canonical, domain, config.get("mode", "inference"))


def integrar(config, output_dir=None):
    domains = [d for d in config["mapping"] if _domain_available(config, d)]
    results = {}
    summary = {
        "schema_version": 1,
        "mode": config.get("mode", "inference"),
        "source_type": config["source"]["type"],
        "domains": {},
        "contains_secrets": False,
    }

    with _managed_connector(crear_connector(config)) as connector:
        for domain in domains:
            df = integrar_dominio(config, connector, domain)
            results[domain] = df
            summary["domains"][domain] = {
                "rows": int(len(df)),
                "columns": list(df.columns),
            }

    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for domain, df in results.items():
            df.to_csv(out / f"{domain}.csv", index=False)
        (out / "integration_manifest.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return results, summary


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
            f"CONFIG OK | mode={config.get('mode', 'inference')} | "
            f"source={config['source']['type']} | domains={sorted(config['mapping'])}"
        )
        return

    _, summary = integrar(config, output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
