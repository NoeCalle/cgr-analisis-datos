"""Regresiones arquitectónicas del Sprint 2: TRAIN nunca debe filtrarse a INFERENCE."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.config import cargar_config
from preprocesamiento import (
    PREPROCESSOR_SCHEMA_VERSION,
    ajustar_estado_preprocesamiento,
    features_favoritismo,
    features_fraccionamiento,
    preparar_para_features_entrenamiento,
    preparar_para_features_inferencia,
)
from registro_modelos import promover_candidato


FAV_FEATURES = [
    "n_contratos", "monto_total", "monto_promedio", "n_objetos_unicos",
    "pct_contratacion_directa", "pct_comparacion_precios",
    "n_funcionarios_distintos", "dias_actividad", "concentracion_objeto",
    "contratos_por_mes", "monto_por_funcionario",
]


def _contracts_base():
    return pd.DataFrame(
        {
            "id_contrato": ["C1", "C2", "C3", "C4"],
            "id_proveedor": ["P1", "P1", "P2", "P2"],
            "id_entidad": ["E1", "E1", "E1", "E1"],
            "id_funcionario": ["F1", "F1", "F2", "F3"],
            "monto": [100.0, 200.0, 300.0, None],
            "fecha_contrato": pd.to_datetime(["2026-01-01", "2026-01-03", "2026-01-05", "2026-01-07"]),
            "modalidad": ["Contratación Directa", "Licitación Pública", None, "Licitación Pública"],
            "objeto": ["A", "A", "B", "B"],
            "categoria_principal": ["goods", "goods", "services", "services"],
        }
    )


def test_preprocesamiento_inference_usa_estado_train_y_no_recalcula():
    train = _contracts_base()
    estado = ajustar_estado_preprocesamiento(train)
    assert estado["schema_version"] == PREPROCESSOR_SCHEMA_VERSION

    # Lote deliberadamente extremo. Un refit sobre inference produciría estadísticas distintas.
    lote = pd.DataFrame(
        {
            "id_contrato": ["N1", "N2"],
            "id_proveedor": ["PX", "PX"],
            "id_entidad": ["EX", "EX"],
            "monto": [None, 9_999_999.0],
            "fecha_contrato": pd.to_datetime(["2026-08-01", "2026-08-02"]),
            "modalidad": [None, "Licitación Pública"],
            "objeto": ["OBJETO_NUEVO", "OBJETO_NUEVO"],
        }
    )
    scored = preparar_para_features_inferencia(lote, estado)

    assert scored.loc[0, "monto"] == pytest.approx(estado["monto_mediana_global"])
    assert scored.loc[0, "modalidad"] == estado["modalidad_moda"]
    assert scored["monto_capped"].max() <= estado["monto_p99"]
    assert "id_funcionario" in scored.columns
    assert set(scored["id_funcionario"]) == {"__NO_DISPONIBLE__"}


def test_features_inference_no_requieren_ni_generan_labels():
    train = _contracts_base()
    procesado, estado = preparar_para_features_entrenamiento(train)
    inference = preparar_para_features_inferencia(train, estado)

    fav = features_favoritismo(inference, label_col=None)
    frac = features_fraccionamiento(inference, label_col=None)

    assert not any(c.startswith("label_") for c in fav.columns)
    assert not any(c.startswith("label_") for c in frac.columns)
    assert set(FAV_FEATURES) <= set(fav.columns)


def test_training_config_exige_ground_truth_y_local_inference_no_lo_mapea():
    train_cfg = cargar_config(ROOT / "config" / "local-training.yaml")
    inference_cfg = cargar_config(ROOT / "config" / "local.yaml")

    assert train_cfg["mode"] == "training"
    assert train_cfg["mapping"]["contracts"]["label_favoritismo"] == "es_favoritismo_real"
    assert train_cfg["mapping"]["contracts"]["label_fraccionamiento"] == "es_fraccionamiento_real"
    assert inference_cfg["mode"] == "inference"
    assert "label_favoritismo" not in inference_cfg["mapping"]["contracts"]
    assert "label_fraccionamiento" not in inference_cfg["mapping"]["contracts"]


def test_score_inference_no_contiene_operaciones_fit_ni_clases_de_entrenamiento():
    source = (ROOT / "src" / "score_inference.py").read_text(encoding="utf-8")
    assert ".fit(" not in source
    assert "RandomForestClassifier" not in source
    assert "IsolationForest(" not in source
    assert "StandardScaler(" not in source
    assert "tuning_favoritismo" not in source


def test_dag_inference_no_genera_datos_ni_entrena():
    source = (ROOT / "airflow_home" / "dags" / "dag_inferencia_modelos.py").read_text(encoding="utf-8")
    assert "src/score_inference.py" in source
    for prohibited in [
        "src/generar_datos.py",
        "src/preprocesamiento.py",
        "src/tuning_favoritismo.py",
        "src/modelo_favoritismo.py",
        "src/modelo_fraccionamiento.py",
        "src/entrenar_candidatos.py",
    ]:
        assert prohibited not in source


def test_dag_train_genera_candidate_sin_comando_de_promocion():
    source = (ROOT / "airflow_home" / "dags" / "dag_entrenamiento_modelos.py").read_text(encoding="utf-8")
    assert "src/entrenar_candidatos.py" in source
    assert "--acknowledge-poc-only" not in source
    assert "promover_candidato(" not in source


def test_promocion_exige_reconocimiento_explicito_antes_de_leer_manifest(tmp_path):
    inexistente = tmp_path / "candidate_manifest.json"
    with pytest.raises(ValueError, match="solo para el PoC"):
        promover_candidato(
            inexistente,
            approved_by="tester",
            acknowledge_poc_only=False,
            registry_path=tmp_path / "registry.json",
        )


def test_feature_engineering_train_mantiene_paridad_con_dataset_legacy():
    raw = pd.read_csv(ROOT / "data" / "contratos_siaf_seace.csv", parse_dates=["fecha_contrato"])
    raw["label_favoritismo"] = raw["es_favoritismo_real"]
    procesado, _ = preparar_para_features_entrenamiento(raw)
    nuevo = features_favoritismo(
        procesado,
        label_col="label_favoritismo",
        output_label="label_favoritismo_real",
    ).sort_values(["id_proveedor", "id_entidad"]).reset_index(drop=True)
    legacy = pd.read_csv(ROOT / "data" / "dataset_favoritismo.csv").sort_values(
        ["id_proveedor", "id_entidad"]
    ).reset_index(drop=True)

    assert len(nuevo) == len(legacy)
    for col in FAV_FEATURES:
        assert np.allclose(nuevo[col].astype(float), legacy[col].astype(float), rtol=1e-10, atol=1e-10)
    assert nuevo["label_favoritismo_real"].astype(int).tolist() == legacy["label_favoritismo_real"].astype(int).tolist()
