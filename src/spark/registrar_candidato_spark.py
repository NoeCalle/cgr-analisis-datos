"""Construye el manifest candidate de la ruta Spark MLlib.

Este paso NO promueve nada. Solo toma los modelos runtime ajustados por la
corrida TRAIN Spark, añade el estado de preprocesamiento framework-neutral y
registra hashes verificables para una promoción explícita posterior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from registro_modelos import guardar_json_determinista, sha256_ruta

DEFAULT_MANIFEST = Path("outputs/runtime/spark_model_candidates/candidate_manifest.json")
SKLEARN_CANDIDATE = Path("outputs/runtime/model_candidates/candidate_manifest.json")
PREPROCESSOR_JSON = Path("outputs/runtime/model_candidates/preprocesador_contratos.json")
FAV_MODEL = Path("outputs/runtime/modelo_favoritismo_spark_rf")
FRAC_MODEL = Path("outputs/runtime/modelo_fraccionamiento_spark_kmeans")
FRAC_SCALER = Path("outputs/runtime/modelo_fraccionamiento_spark_scaler")
FAV_SUMMARY = Path("outputs/spark_favoritismo_resumen.json")
FRAC_SUMMARY = Path("outputs/spark_fraccionamiento_resumen.json")


def registrar(manifest_path: str | Path = DEFAULT_MANIFEST) -> dict:
    requeridos = [
        SKLEARN_CANDIDATE,
        PREPROCESSOR_JSON,
        FAV_MODEL,
        FRAC_MODEL,
        FRAC_SCALER,
        FAV_SUMMARY,
        FRAC_SUMMARY,
    ]
    faltantes = [str(p) for p in requeridos if not p.exists()]
    if faltantes:
        raise FileNotFoundError(f"No se puede registrar candidate Spark; faltan: {faltantes}")

    training_base = json.loads(SKLEARN_CANDIDATE.read_text(encoding="utf-8"))
    fav_summary = json.loads(FAV_SUMMARY.read_text(encoding="utf-8"))
    frac_summary = json.loads(FRAC_SUMMARY.read_text(encoding="utf-8"))

    artifacts = {
        "preprocessor_json": {
            "path": PREPROCESSOR_JSON.as_posix(),
            "sha256": sha256_ruta(PREPROCESSOR_JSON),
            "kind": "file",
        },
        "favoritismo_model": {
            "path": FAV_MODEL.as_posix(),
            "sha256": sha256_ruta(FAV_MODEL),
            "kind": "spark_model_directory",
        },
        "fraccionamiento_model": {
            "path": FRAC_MODEL.as_posix(),
            "sha256": sha256_ruta(FRAC_MODEL),
            "kind": "spark_model_directory",
        },
        "fraccionamiento_scaler": {
            "path": FRAC_SCALER.as_posix(),
            "sha256": sha256_ruta(FRAC_SCALER),
            "kind": "spark_model_directory",
        },
    }

    identity = {
        "training_data": training_base["training"]["training_data_fingerprint_sha256"],
        "artifacts": {k: v["sha256"] for k, v in artifacts.items()},
        "favoritismo_config": fav_summary["mejor_configuracion"],
        "fraccionamiento_k": frac_summary["k"],
    }
    candidate_hash = hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    manifest = {
        "schema_version": 1,
        "status": "candidate",
        "engine": "spark_mllib",
        "candidate_id": f"spark-poc-{candidate_hash[:16]}",
        "nature": "candidato Spark MLlib del PoC; no aprobado para infraestructura CGR",
        "training": {
            **training_base["training"],
            "engine": "Apache Spark MLlib",
            "spark_mode": "local[*]",
            "ground_truth_required": True,
            "validation_evidence": [
                "outputs/spark_favoritismo_resumen.json",
                "outputs/spark_fraccionamiento_resumen.json",
                "outputs/comparacion_modelos_favoritismo.json",
                "outputs/tuning_fraccionamiento_resumen.json",
            ],
        },
        "models": {
            "favoritismo": {
                "framework": "Apache Spark MLlib",
                "algorithm": "RandomForestClassificationModel",
                "features": fav_summary["features"],
                "label": "label_favoritismo",
                "params": fav_summary["mejor_configuracion"],
            },
            "fraccionamiento": {
                "framework": "Apache Spark MLlib",
                "algorithm": "StandardScalerModel + KMeansModel + distancia al centroide",
                "features": frac_summary["features"],
                "label": "label_fraccionamiento",
                "params": {"k": frac_summary["k"]},
            },
        },
        "artifacts": artifacts,
    }
    guardar_json_determinista(manifest_path, manifest)
    print(f"Candidate Spark generado: {manifest['candidate_id']}")
    print("Estado: candidate. El champion no fue modificado.")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Registra candidate Spark sin promoverlo.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    registrar(args.manifest)


if __name__ == "__main__":
    main()
