"""Pruebas Sprint 1: fuente intercambiable -> mapping -> esquema canónico."""

import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from connectors.local_csv import LocalCsvConnector
from connectors.sqlserver import _quote_identifier, _quote_qualified_identifier
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
        mapping["label_favoritismo"] = "GT_FAV"
        mapping["label_fraccionamiento"] = "GT_FRAC"
    return mapping


def test_mapping_arbitrario_produce_esquema_canonico_inference_sin_labels():
    canonical = aplicar_mapping(_source_df(), "contracts", _mapping())
    validated = validar_dataframe(canonical, "contracts", mode="inference")

    assert list(validated.columns) == list(_mapping())
    assert validated["id_contrato"].tolist() == ["X-001", "X-002"]
    assert pd.api.types.is_datetime64_any_dtype(validated["fecha_contrato"])
    assert "label_favoritismo" not in validated.columns
    assert "label_fraccionamiento" not in validated.columns


def test_training_exige_ground_truth_pero_inference_no():
    canonical = aplicar_mapping(_source_df(), "contracts", _mapping())
    validar_dataframe(canonical, "contracts", mode="inference")

    with pytest.raises(ValueError, match="label_favoritismo"):
        validar_dataframe(canonical, "contracts", mode="training")

    canonical_train = aplicar_mapping(_source_df(True), "contracts", _mapping(True))
    validated_train = validar_dataframe(canonical_train, "contracts", mode="training")
    assert validated_train["label_favoritismo"].astype(bool).tolist() == [False, True]


def test_training_rechaza_label_nulo():
    source = _source_df(True)
    source.loc[0, "GT_FAV"] = None
    canonical = aplicar_mapping(source, "contracts", _mapping(True))
    with pytest.raises(ValueError, match="label_favoritismo contiene 1 nulos"):
        validar_dataframe(canonical, "contracts", mode="training")


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


def test_config_rechaza_mapping_sin_ubicacion_de_fuente():
    config = {
        "mode": "inference",
        "source": {
            "type": "local_csv",
            "datasets": {"contracts": "contratos.csv"},
        },
        "mapping": {
            "contracts": _mapping(),
            "suppliers": {"id_proveedor": "COD_PROV"},
        },
    }
    with pytest.raises(ValueError, match="mappings sin fuente"):
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
    assert "label_favoritismo" not in results["contracts"].columns


def test_fuente_con_columnas_arbitrarias_funciona_cambiando_solo_yaml(tmp_path):
    csv_path = tmp_path / "tb_contratacion.csv"
    config_path = tmp_path / "institucion.yaml"
    _source_df().to_csv(csv_path, index=False)

    config_path.write_text(
        yaml.safe_dump(
            {
                "mode": "inference",
                "source": {
                    "type": "local_csv",
                    "datasets": {"contracts": str(csv_path)},
                },
                "mapping": {"contracts": _mapping()},
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    config = cargar_config(config_path)
    results, summary = integrar(config)
    contracts = results["contracts"]

    assert summary["source_type"] == "local_csv"
    assert contracts["id_proveedor"].tolist() == ["SUP-9", "SUP-8"]
    assert contracts["monto"].tolist() == [125000.50, 98000.00]
    assert list(contracts.columns) == list(_mapping())


def test_local_csv_lee_solo_columnas_mapeadas_y_preserva_ceros(tmp_path):
    path = tmp_path / "contratos.csv"
    df = _source_df()
    df.loc[0, "COD_PROV"] = "000123"
    df["COLUMNA_QUE_NO_NECESITAMOS"] = "ignorar"
    df.to_csv(path, index=False)

    connector = LocalCsvConnector({"contracts": str(path)})
    out = connector.read("contracts", list(_mapping().values()))
    assert "COLUMNA_QUE_NO_NECESITAMOS" not in out.columns
    assert out.loc[0, "COD_PROV"] == "000123"


def test_sqlserver_escapa_identificadores_y_rechaza_sql_libre():
    assert _quote_identifier("Monto Adjudicado") == "[Monto Adjudicado]"
    assert _quote_qualified_identifier("dbo.Vista Contratos") == "[dbo].[Vista Contratos]"
    with pytest.raises(ValueError, match="no permitido"):
        _quote_identifier("monto; DROP TABLE x")
