"""Regresiones arquitectónicas: TRAIN nunca debe filtrarse a INFERENCE."""

import json
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
    codificar_y_normalizar,
    features_favoritismo,
    features_fraccionamiento,
    limpiar_e_imputar,
    preparar_para_features_entrenamiento,
    preparar_para_features_inferencia,
)
from registro_modelos import (
    REGISTRY_SCHEMA_VERSION,
    SKLEARN_PROFILE,
    cargar_registry_unificado,
    promover_candidato,
    promover_candidato_spark,
    sha256_ruta,
)


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


def test_train_nuevo_preserva_monto_valido_aunque_objeto_sea_nulo():
    raw = pd.read_csv(ROOT / "data" / "contratos_siaf_seace.csv", parse_dates=["fecha_contrato"])
    caso = raw.loc[raw["id_contrato"] == "C002938"].copy()
    assert len(caso) == 1
    assert pd.isna(caso.iloc[0]["objeto"])
    monto_original = float(caso.iloc[0]["monto"])
    assert monto_original == pytest.approx(117888.71)

    estado = ajustar_estado_preprocesamiento(raw)
    transformado = preparar_para_features_inferencia(caso, estado)
    assert float(transformado.iloc[0]["monto"]) == pytest.approx(monto_original)


def test_features_inference_no_requieren_ni_generan_labels():
    train = _contracts_base()
    _, estado = preparar_para_features_entrenamiento(train)
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


def test_score_inference_sklearn_no_contiene_fit():
    source = (ROOT / "src" / "score_inference.py").read_text(encoding="utf-8")
    assert ".fit(" not in source
    assert "RandomForestClassifier" not in source
    assert "IsolationForest(" not in source
    assert "StandardScaler(" not in source
    assert "tuning_favoritismo" not in source


def test_score_inference_spark_es_transform_puro_y_sin_sklearn():
    source = (ROOT / "src" / "spark" / "score_inference_spark.py").read_text(encoding="utf-8")
    assert ".fit(" not in source
    assert "RandomForestClassifier(" not in source
    assert "KMeans(" not in source
    assert "StandardScaler(" not in source
    assert "sklearn" not in source.lower()
    assert "joblib" not in source.lower()
    assert "RandomForestClassificationModel.load" in source
    assert "KMeansModel.load" in source
    assert "StandardScalerModel.load" in source


def test_preprocesamiento_serving_spark_no_aprende_parametros():
    source = (ROOT / "src" / "spark" / "preprocesamiento_serving_spark.py").read_text(
        encoding="utf-8"
    )
    assert ".fit(" not in source
    assert "StandardScaler(" not in source
    assert "OneHotEncoder(" not in source
    assert "ajustar_estado_preprocesamiento" not in source


def test_dag_inference_usa_spark_y_no_genera_datos_ni_entrena():
    source = (ROOT / "airflow_home" / "dags" / "dag_inferencia_modelos.py").read_text(
        encoding="utf-8"
    )
    assert "src/spark/score_inference_spark.py" in source
    for prohibited in [
        "src/generar_datos.py",
        "src/preprocesamiento.py",
        "src/tuning_favoritismo.py",
        "src/modelo_favoritismo.py",
        "src/modelo_fraccionamiento.py",
        "src/entrenar_candidatos.py",
        "src/spark/entrenar_candidato_spark.py",
    ]:
        assert prohibited not in source


def test_dag_train_genera_candidate_spark_sin_promocion():
    source = (ROOT / "airflow_home" / "dags" / "dag_entrenamiento_modelos.py").read_text(
        encoding="utf-8"
    )
    assert "src/spark/entrenar_candidato_spark.py" in source
    assert "--acknowledge-poc-only" not in source
    assert "promover_candidato" not in source


def test_train_spark_no_consume_plata_legacy_para_serving():
    source = (ROOT / "src" / "spark" / "entrenar_candidato_spark.py").read_text(encoding="utf-8")
    assert "integrar(config)" in source
    assert "ajustar_estado_preprocesamiento(contracts)" in source
    assert "lakehouse/plata/contratos_procesados.csv" not in source
    assert "outputs/runtime/spark_model_candidates" in source


def test_promocion_exige_reconocimiento_explicito_antes_de_leer_manifest(tmp_path):
    inexistente = tmp_path / "candidate_manifest.json"
    with pytest.raises(ValueError, match="solo para el PoC"):
        promover_candidato(
            inexistente,
            approved_by="tester",
            acknowledge_poc_only=False,
            registry_path=tmp_path / "registry.json",
        )


def test_promocion_spark_exige_reconocimiento_explicito(tmp_path):
    inexistente = tmp_path / "spark_candidate_manifest.json"
    with pytest.raises(ValueError, match="solo para el PoC"):
        promover_candidato_spark(
            inexistente,
            approved_by="tester",
            acknowledge_poc_only=False,
            registry_path=tmp_path / "registry.json",
        )


def test_registry_v1_migra_en_memoria_a_perfil_sklearn(tmp_path):
    legacy = {
        "schema_version": 1,
        "status": "champion",
        "champion_id": "legacy-1",
        "promotion": {"institutional_approval": False},
        "training": {"ground_truth_required": True},
        "models": {},
        "artifacts": {},
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")
    migrated = cargar_registry_unificado(path)
    assert migrated["schema_version"] == REGISTRY_SCHEMA_VERSION == 2
    assert migrated["active_serving_profile"] == SKLEARN_PROFILE
    assert migrated["serving_profiles"][SKLEARN_PROFILE]["champion_id"] == "legacy-1"


def test_hash_directorio_spark_ignora_crc(tmp_path):
    model_dir = tmp_path / "modelo"
    (model_dir / "metadata").mkdir(parents=True)
    (model_dir / "data").mkdir()
    (model_dir / "metadata" / "part-00000").write_text("abc", encoding="utf-8")
    (model_dir / "data" / "part-00000.parquet").write_bytes(b"payload")
    antes = sha256_ruta(model_dir)
    (model_dir / "metadata" / ".part-00000.crc").write_bytes(b"local-hadoop-crc")
    assert sha256_ruta(model_dir) == antes


def test_ruta_legacy_reproduce_dataset_favoritismo_rc1():
    """Congela la evidencia RC1 sin obligar al serving nuevo a heredar su bug."""
    raw = pd.read_csv(ROOT / "data" / "contratos_siaf_seace.csv", parse_dates=["fecha_contrato"])
    legacy_reconstruido = codificar_y_normalizar(limpiar_e_imputar(raw))
    nuevo_legacy = features_favoritismo(
        legacy_reconstruido,
        label_col="es_favoritismo_real",
        output_label="label_favoritismo_real",
    ).sort_values(["id_proveedor", "id_entidad"]).reset_index(drop=True)
    legacy_versionado = pd.read_csv(ROOT / "data" / "dataset_favoritismo.csv").sort_values(
        ["id_proveedor", "id_entidad"]
    ).reset_index(drop=True)

    assert len(nuevo_legacy) == len(legacy_versionado) == 2328
    for col in FAV_FEATURES:
        assert np.allclose(
            nuevo_legacy[col].astype(float),
            legacy_versionado[col].astype(float),
            rtol=1e-10,
            atol=1e-10,
            equal_nan=True,
        ), col
    assert nuevo_legacy["label_favoritismo_real"].astype(int).tolist() == legacy_versionado[
        "label_favoritismo_real"
    ].astype(int).tolist()
