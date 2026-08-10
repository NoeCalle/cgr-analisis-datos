"""Carga y validación de configuración para fuentes institution-ready.

La configuración puede versionarse siempre que contenga solo referencias a
variables de entorno para credenciales. Secrets inline se rechazan.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import yaml

from core.schemas import SCHEMAS, campos_canonicos, campos_requeridos

ALLOWED_SOURCE_TYPES = {"local_csv", "sqlserver", "spark_sql"}
CANONICAL_SCHEMA_VERSION = 1
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


def obtener_version_contrato(config: dict[str, Any]) -> int:
    """Devuelve la versión canónica, preservando compatibilidad con configs v1 antiguas."""
    version = config.get("contract_schema_version", CANONICAL_SCHEMA_VERSION)
    if type(version) is not int or version != CANONICAL_SCHEMA_VERSION:
        raise ValueError(
            "contract_schema_version incompatible: "
            f"{version!r}; esta versión del código soporta {CANONICAL_SCHEMA_VERSION}."
        )
    return version


def validar_config(config: dict[str, Any]) -> None:
    _rechazar_secrets_inline(config)
    obtener_version_contrato(config)

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
        if not all(isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip() for k, v in domain_mapping.items()):
            raise ValueError(f"mapping.{domain} solo admite nombres de columna no vacíos.")

        unknown_fields = set(domain_mapping) - set(campos_canonicos(domain))
        if unknown_fields:
            raise ValueError(
                f"mapping.{domain} contiene campos canónicos desconocidos: {sorted(unknown_fields)}"
            )

        physical = list(domain_mapping.values())
        duplicated_physical = sorted({c for c in physical if physical.count(c) > 1})
        if duplicated_physical:
            raise ValueError(
                f"mapping.{domain} reutiliza columnas físicas para varios campos: {duplicated_physical}"
            )

        missing = set(campos_requeridos(domain, mode)) - set(domain_mapping)
        # Si un dominio se configura, su contrato mínimo debe ser ejecutable.
        # Para omitir una dimensión todavía no disponible, se omite el dominio
        # completo del mapping y de la fuente; no se acepta una configuración
        # que pase --validate-only pero falle al leer el DataFrame real.
        if missing:
            raise ValueError(
                f"mapping.{domain} no define campos obligatorios para {mode}: {sorted(missing)}"
            )

    location_key = "datasets" if source_type == "local_csv" else "tables"
    locations = source.get(location_key)
    if not isinstance(locations, dict) or "contracts" not in locations:
        raise ValueError(f"source.{location_key}.contracts es obligatorio para {source_type}.")

    unknown_locations = set(locations) - set(SCHEMAS)
    if unknown_locations:
        raise ValueError(
            f"Dominios desconocidos en source.{location_key}: {sorted(unknown_locations)}"
        )
    missing_locations = domains_configured - set(locations)
    if missing_locations:
        raise ValueError(
            f"Hay mappings sin fuente configurada en source.{location_key}: {sorted(missing_locations)}"
        )
    if not all(isinstance(v, str) and v.strip() for v in locations.values()):
        raise ValueError(f"source.{location_key} solo admite rutas/tablas no vacías.")

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
