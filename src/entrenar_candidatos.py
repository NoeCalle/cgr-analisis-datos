"""TRAIN explícito del Sprint 2/Sprint 3/Sprint 4.

Lee una fuente configurada en `mode: training`, ajusta el preprocesador una sola
vez y entrena artefactos candidatos sklearn. No escribe el registry champion y
no puede habilitar serving por sí mismo.

Sprint 3 añade una copia JSON del estado de preprocesamiento. Sprint 4 hace que
el favoritismo operacional consuma ``monto_capped`` (P99 aprendido en TRAIN),
mientras la ruta legacy permanece separada para reproducir RC1.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from core.config import cargar_config
from core.security_paths import preparar_directorio_candidato
from ingestar_canonico import integrar
from modelo_favoritismo import DEFAULT_PARAMS as FAV_DEFAULT_PARAMS
from modelo_favoritismo import FEATURES as FAV_FEATURES
from modelo_favoritismo import parametros_seleccionados as parametros_favoritismo
from modelo_fraccionamiento import DEFAULT_PARAMS as FRAC_DEFAULT_PARAMS
from modelo_fraccionamiento import FEATURES as FRAC_FEATURES
from modelo_fraccionamiento import parametros_seleccionados as parametros_fraccionamiento
from preprocesamiento import (
    features_favoritismo,
    features_fraccionamiento,
    preparar_para_features_entrenamiento,
)
from registro_modelos import guardar_json_determinista, sha256_ruta

DEFAULT_MANIFEST = Path("outputs/runtime/model_candidates/candidate_manifest.json")
FAVORITISMO_MONTO_OPERACIONAL = "monto_capped"


def _fingerprint_dataframe(df: pd.DataFrame) -> str:
    normalized = df.copy()
    for col in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[col]):
            normalized[col] = normalized[col].dt.strftime("%Y-%m-%dT%H:%M:%S")
    csv_bytes = normalized.to_csv(index=False, na_rep="<NA>").encode("utf-8")
    return hashlib.sha256(csv_bytes).hexdigest()


def _jsonable_params(params: dict) -> dict:
    result = {}
    for key, value in params.items():
        if hasattr(value, "item"):
            value = value.item()
        result[key] = value
    return result


def entrenar(config_path: str | Path, manifest_path: str | Path = DEFAULT_MANIFEST) -> dict:
    config = cargar_config(config_path)
    if config.get("mode") != "training":
        raise ValueError("TRAIN requiere una configuración con mode: training.")

    datasets, integration_summary = integrar(config)
    contracts = datasets["contracts"]
    if "label_favoritismo" not in contracts or "label_fraccionamiento" not in contracts:
        raise ValueError("La fuente TRAIN debe entregar ambos ground truths canónicos.")

    procesado, estado = preparar_para_features_entrenamiento(contracts)
    fav = features_favoritismo(
        procesado,
        label_col="label_favoritismo",
        output_label="label_favoritismo",
        monto_col=FAVORITISMO_MONTO_OPERACIONAL,
    )
    frac = features_fraccionamiento(
        procesado,
        label_col="label_fraccionamiento",
        output_label="label_fraccionamiento",
    )

    params_fav = _jsonable_params(
        parametros_favoritismo()
        if Path("outputs/tuning_favoritismo_resumen.json").exists()
        else FAV_DEFAULT_PARAMS
    )
    params_frac = _jsonable_params(
        parametros_fraccionamiento()
        if Path("outputs/tuning_fraccionamiento_resumen.json").exists()
        else FRAC_DEFAULT_PARAMS
    )

    fav_model = RandomForestClassifier(
        **params_fav,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    fav_model.fit(fav[FAV_FEATURES], fav["label_favoritismo"].astype(int))

    frac_scaler = StandardScaler().fit(frac[FRAC_FEATURES])
    frac_scaled = frac_scaler.transform(frac[FRAC_FEATURES])
    frac_model = IsolationForest(**params_frac, random_state=42)
    frac_model.fit(frac_scaled)

    manifest_path, candidate_dir = preparar_directorio_candidato(manifest_path)

    artifact_paths = {
        "preprocessor": candidate_dir / "preprocesador_contratos.joblib",
        "preprocessor_json": candidate_dir / "preprocesador_contratos.json",
        "favoritismo_model": candidate_dir / "modelo_favoritismo_rf.joblib",
        "fraccionamiento_model": candidate_dir / "modelo_fraccionamiento_isoforest.joblib",
        "fraccionamiento_scaler": candidate_dir / "scaler_fraccionamiento.joblib",
    }
    joblib.dump(estado, artifact_paths["preprocessor"])
    guardar_json_determinista(artifact_paths["preprocessor_json"], estado)
    joblib.dump(fav_model, artifact_paths["favoritismo_model"])
    joblib.dump(frac_model, artifact_paths["fraccionamiento_model"])
    joblib.dump(frac_scaler, artifact_paths["fraccionamiento_scaler"])

    data_fingerprint = _fingerprint_dataframe(contracts)
    identity_payload = {
        "data": data_fingerprint,
        "fav_features": FAV_FEATURES,
        "fav_amount_source": FAVORITISMO_MONTO_OPERACIONAL,
        "frac_features": FRAC_FEATURES,
        "fav_params": params_fav,
        "frac_params": params_frac,
        "preprocessor_schema": estado["schema_version"],
    }
    candidate_hash = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    candidate_id = f"poc-{candidate_hash[:16]}"

    manifest = {
        "schema_version": 1,
        "status": "candidate",
        "candidate_id": candidate_id,
        "nature": "candidato técnico del PoC; no aprobado para infraestructura CGR",
        "training": {
            "config": str(config_path),
            "source_type": integration_summary["source_type"],
            "training_data_fingerprint_sha256": data_fingerprint,
            "contracts_rows": int(len(contracts)),
            "favoritismo_rows": int(len(fav)),
            "favoritismo_positives": int(fav["label_favoritismo"].astype(int).sum()),
            "favoritismo_amount_source": FAVORITISMO_MONTO_OPERACIONAL,
            "fraccionamiento_rows": int(len(frac)),
            "fraccionamiento_positives": int(frac["label_fraccionamiento"].astype(int).sum()),
            "fraccionamiento_amount_source": "monto",
            "ground_truth_required": True,
            "validation_evidence": [
                "outputs/comparacion_modelos_favoritismo.json",
                "outputs/tuning_favoritismo_resumen.json",
                "outputs/tuning_fraccionamiento_resumen.json",
            ],
        },
        "models": {
            "favoritismo": {
                "framework": "scikit-learn",
                "algorithm": "RandomForestClassifier",
                "features": FAV_FEATURES,
                "amount_source": FAVORITISMO_MONTO_OPERACIONAL,
                "label": "label_favoritismo",
                "params": params_fav,
            },
            "fraccionamiento": {
                "framework": "scikit-learn",
                "algorithm": "IsolationForest + StandardScaler",
                "features": FRAC_FEATURES,
                "amount_source": "monto",
                "label": "label_fraccionamiento",
                "params": params_frac,
            },
        },
        "artifacts": {
            name: {"path": path.as_posix(), "sha256": sha256_ruta(path)}
            for name, path in artifact_paths.items()
        },
    }
    guardar_json_determinista(manifest_path, manifest)
    print(f"Candidate generado: {candidate_id}")
    print(f"Manifest: {manifest_path}")
    print("Estado: candidate. No se ha promovido ningún modelo para inference.")
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Entrena candidatos sin promoverlos a champion.")
    parser.add_argument("--config", default="config/local-training.yaml")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    entrenar(args.config, args.manifest)


if __name__ == "__main__":
    main()