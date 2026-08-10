"""Regresiones del contrato YAML y su validación offline."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.config import (
    CANONICAL_SCHEMA_VERSION,
    cargar_config,
    obtener_version_contrato,
    validar_config,
)


def _contracts_mapping():
    return {
        "id_contrato": "ID_CONTRATO",
        "id_proveedor": "ID_PROVEEDOR",
        "id_entidad": "ID_ENTIDAD",
        "monto": "MONTO",
        "fecha_contrato": "FECHA",
        "modalidad": "MODALIDAD",
        "objeto": "OBJETO",
        "categoria_principal": "CATEGORIA",
    }


def test_validate_only_rechaza_dimension_configurada_sin_clave_obligatoria():
    config = {
        "contract_schema_version": 1,
        "mode": "inference",
        "source": {
            "type": "local_csv",
            "datasets": {
                "contracts": "contracts.csv",
                "suppliers": "suppliers.csv",
            },
        },
        "mapping": {
            "contracts": _contracts_mapping(),
            "suppliers": {"nombre_proveedor": "NOMBRE_PROVEEDOR"},
        },
    }
    with pytest.raises(ValueError, match=r"mapping\.suppliers.*id_proveedor"):
        validar_config(config)


def test_version_contrato_rechaza_version_incompatible():
    config = {
        "contract_schema_version": 999,
        "mode": "inference",
        "source": {"type": "local_csv", "datasets": {"contracts": "contracts.csv"}},
        "mapping": {"contracts": _contracts_mapping()},
    }
    with pytest.raises(ValueError, match="contract_schema_version incompatible"):
        validar_config(config)


def test_version_contrato_v1_es_explicita_en_configs_versionadas():
    assert CANONICAL_SCHEMA_VERSION == 1
    for name in ["local.yaml", "local-training.yaml", "local-tdr.yaml", "cgr.example.yaml"]:
        config = cargar_config(ROOT / "config" / name)
        assert config["contract_schema_version"] == 1
        assert obtener_version_contrato(config) == 1


def test_config_legacy_sin_version_se_interpreta_como_v1():
    config = {
        "mode": "inference",
        "source": {"type": "local_csv", "datasets": {"contracts": "contracts.csv"}},
        "mapping": {"contracts": _contracts_mapping()},
    }
    validar_config(config)
    assert obtener_version_contrato(config) == 1
