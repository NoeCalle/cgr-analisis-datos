"""Carga y validación de configuración para fuentes institution-ready.

La configuración puede versionarse siempre que contenga solo referencias a
variables de entorno para credenciales. Secrets inline se rechazan.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import yaml

from core.schemas import SCHEMAS, campos_requeridos

ALLOWED_SOURCE_TYPES = {"local_csv", "sqlserver", "spark_sql"}
SECRET_KEY_PATTERN = re.compile(r"(^|_)(password|passwd|pwd|token|secret|api_key|connection_string)($|_)", re.I)
ENV_REFERENCE_SUFFIXES = ("_env", "env")


def cargar_config(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No existe archivo de configuración: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("La configuración raíz debe ser un objeto YAML.")
    validar_config(data)
    return data


def validar_config(config: dict[str, Any]) -> None:
    _rechazar_secrets_inline(config)

    source = config.get("source")
    if not isinstance(source, dict):
        raise ValueError("Falta sección 'source'.")
    source_type = source.get("type")
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise ValueError(
            f"source.type inválido {source_type!r}; válidos: {sorted(ALLOWED_SOURCE_TYPES)}"
        )

    mode = config.get("mode", "inference")
    if mode not in {"inference", "training"}:
        raise ValueError("mode debe ser 'inference' o 'training'.")

    mapping = config.get("mapping")
    if not isinstance(mapping, dict) or "contracts" not in mapping:
        raise ValueError("La configuración debe definir mapping.contracts.")

    domains_configured = set(mapping)
    unknown_domains = domains_configured - set(SCHEMAS)
    if unknown_domains:
        raise ValueError(f"Dominios de mapping desconocidos: {sorted(unknown_domains)}")

    for domain, domain_mapping in mapping.items():
        if not isinstance(domain_mapping, dict) or not domain_mapping:
            raise ValueError(f"mapping.{domain} debe ser un objeto no vacío.")
        missing = set(campos_requeridos(domain, mode)) - set(domain_mapping)
        # Solo contracts es obligatorio en Sprint 1; dimensiones pueden mapearse
        # parcialmente hasta que la fuente real sea conocida.
        if domain == "contracts" and missing:
            raise ValueError(
                f"mapping.contracts no define campos obligatorios para {mode}: {sorted(missing)}"
            )

    if source_type == "local_csv":
        datasets = source.get("datasets")
        if not isinstance(datasets, dict) or "contracts" not in datasets:
            raise ValueError("source.datasets.contracts es obligatorio para local_csv.")
    else:
        tables = source.get("tables")
        if not isinstance(tables, dict) or "contracts" not in tables:
            raise ValueError(f"source.tables.contracts es obligatorio para {source_type}.")

    if source_type == "sqlserver":
        env_name = source.get("connection_env")
        if not isinstance(env_name, str) or not env_name.strip():
            raise ValueError("source.connection_env es obligatorio para sqlserver.")


def _rechazar_secrets_inline(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_str = str(key)
            normalized = key_str.lower()
            if SECRET_KEY_PATTERN.search(normalized) and not normalized.endswith(ENV_REFERENCE_SUFFIXES):
                dotted = ".".join((*path, key_str))
                raise ValueError(
                    f"Secret inline no permitido en {dotted!r}. Use una referencia *_env a variable de entorno."
                )
            _rechazar_secrets_inline(child, (*path, key_str))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _rechazar_secrets_inline(child, (*path, str(index)))
