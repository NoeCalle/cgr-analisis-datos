"""Regresiones puntuales del hardening MLOps de la etapa 3B."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from registro_modelos import promover_candidato_spark, sha256_ruta
from spark.entrenar_candidato_spark import _leer_evidencia_para_corpus


def test_train_rechaza_evidencia_de_otro_corpus(tmp_path):
    evidence = tmp_path / "tuning.json"
    evidence.write_text(
        json.dumps({
            "schema_version": 2,
            "training_data_fingerprint_sha256": "corpus-A",
            "mejor_configuracion": {"numTrees": 100, "maxDepth": 3},
        }),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="otro corpus"):
        _leer_evidencia_para_corpus(evidence, "corpus-B")


def test_candidate_spark_pendiente_no_puede_promoverse(tmp_path):
    base = tmp_path / "candidate"
    base.mkdir()
    artifacts = {}
    for name in [
        "preprocessor_json",
        "favoritismo_model",
        "fraccionamiento_model",
        "fraccionamiento_scaler",
    ]:
        path = base / name
        path.write_text(name, encoding="utf-8")
        artifacts[name] = {"path": path.as_posix(), "sha256": sha256_ruta(path)}

    manifest = {
        "schema_version": 2,
        "status": "candidate",
        "engine": "spark_mllib",
        "candidate_id": "spark-poc-pending-test",
        "training": {
            "validation_state": "pending_candidate_evaluation",
            "training_data_fingerprint_sha256": "new-corpus",
        },
        "models": {"favoritismo": {}, "fraccionamiento": {}},
        "artifacts": artifacts,
    }
    manifest_path = base / "candidate_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="pendiente de evaluación"):
        promover_candidato_spark(
            manifest_path,
            approved_by="tester",
            acknowledge_poc_only=True,
            registry_path=tmp_path / "registry.json",
            store_root=tmp_path / "store",
        )
    assert not (tmp_path / "registry.json").exists()


def test_candidate_spark_evaluado_mismo_corpus_supera_gate_de_manifest(tmp_path):
    """El loader acepta schema 2 evaluado; no prueba modelos Spark reales."""
    base = tmp_path / "candidate-ok"
    base.mkdir()
    artifacts = {}
    for name in [
        "preprocessor_json",
        "favoritismo_model",
        "fraccionamiento_model",
        "fraccionamiento_scaler",
    ]:
        path = base / name
        path.write_text(name, encoding="utf-8")
        artifacts[name] = {"path": path.as_posix(), "sha256": sha256_ruta(path)}

    manifest = {
        "schema_version": 2,
        "status": "candidate",
        "engine": "spark_mllib",
        "candidate_id": "spark-poc-evaluated-test",
        "training": {
            "validation_state": "evaluated_same_corpus",
            "training_data_fingerprint_sha256": "same-corpus",
        },
        "models": {"favoritismo": {}, "fraccionamiento": {}},
        "artifacts": artifacts,
    }
    manifest_path = base / "candidate_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    # La promoción técnica puede materializar artefactos genéricos en este test;
    # el uso real con MLlib queda cubierto por el smoke completo de Actions.
    profile = promover_candidato_spark(
        manifest_path,
        approved_by="tester",
        acknowledge_poc_only=True,
        registry_path=tmp_path / "registry.json",
        store_root=tmp_path / "store",
    )
    assert profile["champion_id"] == "spark-poc-evaluated-test"
    assert profile["promotion"]["artifact_storage"] == "immutable_versioned"
