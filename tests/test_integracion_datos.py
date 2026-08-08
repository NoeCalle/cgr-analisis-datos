"""Pruebas Sprint 1: fuente intercambiable -> mapping -> esquema canónico."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from connectors.local_csv import LocalCsvConnector
from core.config import cargar_config, validar_config
from core.schemas import aplicar_mapping, validar_dataframe
from ingestar_canonico import integrar


def _source_df(include_labels=False):
    data = {
        "NRO_CONTRATO": ["X-001", "X-002"],
        "COD_PROV": ["SUP-9", "SUP-8"],
        "SEC_EJEC": ["ENT-1", "ENT-1"],
        "IMP_ADJ": [125000.50, 98000.00],
        "FEC_SUSC": ["2026-07-01", "2026-07-03"],
        "TIP_PROC": ["Licitación Pública", "Contratación Directa"],
        "DESC_OBJ": ["Bien A", "Servicio B"],
    }
    if include_labels:
        data["GT_FAV"] = [0, 1]
        data["GT_FRAC"] = [0, 0]
    return pd.DataFrame(data)


def _mapping(include_labels=False):
    mapping = {
        "id_contrato": "NRO_CONTRATO",
        "id_proveedor": "COD_PROV",
        "id_entidad": "SEC_EJEC",
        "monto": "IMP_ADJ",
        "fecha_contrato": "FEC_SUSC",
        "modalidad": "TIP_PROC",
        "objeto": "DESC_OBJ",
    }
    if include_labels:
        mapping["es_favoritismo_real"] = "GT_FAV"
        mapping["es_fraccionamiento_real"] = "GT_FRAC"
    return mapping


def test_mapping_arbitrario_produce_esquema_canonico_inference_sin_labels():
    canonical = aplicar_mapping(_source_df(), "contracts", _mapping())
    validated = validar_dataframe(canonical, "contracts", mode="inference")

    assert list(validated.columns) == list(_mapping())
    assert validated["id_contrato"].tolist() == ["X-001", "X-002"]
    assert pd.api.types.is_datetime64_any_dtype(validated["fecha_contrato"])
    assert "es_favoritismo_real" not in validated.columns
    assert "es_fraccionamiento_real" not in validated.columns


def test_training_exige_ground_truth_pero_inference_no():
    canonical = aplicar_mapping(_source_df(), "contracts", _mapping())
    validar_dataframe(canonical, "contracts", mode="inference")

    with pytest.raises(ValueError, match="es_favoritismo_real"):
        validar_dataframe(canonical, "contracts", mode="training")

    canonical_train = aplicar_mapping(_source_df(True), "contracts", _mapping(True))
    validated_train = validar_dataframe(canonical_train, "contracts", mode="training")
    assert validated_train["es_favoritismo_real"].astype(bool).tolist() == [False, True]


def test_mapping_no_permite_una_columna_fisica_para_dos_campos():
    mapping = _mapping()
    mapping["id_entidad"] = "COD_PROV"
    with pytest.raises(ValueError, match="múltiples campos canónicos"):
        aplicar_mapping(_source_df(), "contracts", mapping)


def test_config_rechaza_secret_inline():
    config = {
        "mode": "inference",
        "source": {
            "type": "sqlserver",
            "connection_env": "CGR_DB_URL",
            "password": "no-debe-estar-aqui",
            "tables": {"contracts": "dbo.Contratos"},
        },
        "mapping": {"contracts": _mapping()},
    }
    with pytest.raises(ValueError, match="Secret inline"):
        validar_config(config)


def test_plantilla_cgr_es_valida_y_no_requiere_conexion_para_validarse():
    config = cargar_config(ROOT / "config" / "cgr.example.yaml")
    assert config["source"]["type"] == "sqlserver"
    assert config["source"]["connection_env"] == "CGR_SOURCE_DATABASE_URL"
    assert config["mode"] == "inference"


def test_config_local_integracion_end_to_end_con_datos_sinteticos():
    config = cargar_config(ROOT / "config" / "local.yaml")
    results, summary = integrar(config)

    assert summary["source_type"] == "local_csv"
    assert summary["contains_secrets"] is False
    assert len(results["contracts"]) > 0
    assert {"contracts", "suppliers", "entities", "officials"}.issubset(results)
    assert "es_favoritismo_real" not in results["contracts"].columns


def test_local_csv_lee_solo_columnas_mapeadas(tmp_path):
    path = tmp_path / "contratos.csv"
    df = _source_df()
    df["COLUMNA_QUE_NO_NECESITAMOS"] = "ignorar"
    df.to_csv(path, index=False)

    connector = LocalCsvConnector({"contracts": str(path)})
    out = connector.read("contracts", list(_mapping().values()))
    assert "COLUMNA_QUE_NO_NECESITAMOS" not in out.columns
