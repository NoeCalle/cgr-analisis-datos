"""INFERENCE puro del Sprint 2.

Contrato operacional:
  fuente `mode: inference` -> mapping canónico -> preprocesador champion
  -> features -> modelos champion -> rankings

Este módulo no entrena, no tunea y no requiere labels. Los rankings detallados
se escriben por defecto bajo `outputs/runtime/`, ruta ignorada por Git porque una
fuente institucional puede contener identificadores sensibles.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

from core.config import cargar_config
from ingestar_canonico import integrar
from preprocesamiento import (
    features_favoritismo,
    features_fraccionamiento,
    preparar_para_features_inferencia,
)
from registro_modelos import cargar_registry_champion, guardar_json_determinista, sha256_archivo

DEFAULT_OUTPUT_DIR = Path("outputs/runtime/inference/latest")


def _cargar_artefacto(registry: dict, nombre: str):
    spec = registry["artifacts"][nombre]
    return joblib.load(spec["path"])


def _indice_clase_positiva(modelo) -> int:
    classes = list(modelo.classes_)
    for candidato in (1, True):
        if candidato in classes:
            return classes.index(candidato)
    raise ValueError(f"Champion de favoritismo no contiene clase positiva 1/True: {classes}")


def ejecutar_inference(
    config_path: str | Path,
    registry_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    summary_path: str | Path | None = None,
) -> dict:
    config = cargar_config(config_path)
    if config.get("mode") != "inference":
        raise ValueError("INFERENCE requiere una configuración con mode: inference.")

    datasets, integration_summary = integrar(config)
    contracts = datasets["contracts"]
    labels_present = sorted(
        c for c in contracts.columns if c in {"label_favoritismo", "label_fraccionamiento"}
    )
    if labels_present:
        raise ValueError(
            "INFERENCE no debe consumir ground truth. Quite labels del mapping de la fuente: "
            f"{labels_present}"
        )

    registry = cargar_registry_champion(registry_path)
    preprocessor = _cargar_artefacto(registry, "preprocessor")
    fav_model = _cargar_artefacto(registry, "favoritismo_model")
    frac_model = _cargar_artefacto(registry, "fraccionamiento_model")
    frac_scaler = _cargar_artefacto(registry, "fraccionamiento_scaler")

    funcionario_col_presente = "id_funcionario" in contracts.columns
    funcionarios_nulos_entrada = (
        int(contracts["id_funcionario"].isna().sum()) if funcionario_col_presente else int(len(contracts))
    )

    procesado = preparar_para_features_inferencia(contracts, preprocessor)
    fav = features_favoritismo(procesado, label_col=None)
    frac = features_fraccionamiento(procesado, label_col=None)

    fav_features = registry["models"]["favoritismo"]["features"]
    frac_features = registry["models"]["fraccionamiento"]["features"]
    faltan_fav = sorted(set(fav_features) - set(fav.columns))
    faltan_frac = sorted(set(frac_features) - set(frac.columns))
    if faltan_fav or faltan_frac:
        raise ValueError(
            f"Feature schema incompatible con champion: favoritismo={faltan_fav}, "
            f"fraccionamiento={faltan_frac}"
        )

    positive_index = _indice_clase_positiva(fav_model)
    ranking_fav = fav.copy()
    ranking_fav["score_riesgo_favoritismo"] = fav_model.predict_proba(
        fav[fav_features]
    )[:, positive_index]
    ranking_fav = ranking_fav.sort_values("score_riesgo_favoritismo", ascending=False)

    ranking_frac = frac.copy()
    frac_scaled = frac_scaler.transform(frac[frac_features])
    ranking_frac["score_anomalia"] = -frac_model.decision_function(frac_scaled)
    ranking_frac["es_anomalia_modelo"] = frac_model.predict(frac_scaled) == -1
    ranking_frac["senal_priorizacion_fraccionamiento"] = (
        (ranking_frac["max_contratos_ventana_15d"] >= 3)
        & (ranking_frac["pct_montos_bajo_umbral"] >= 0.7)
    )
    ranking_frac = ranking_frac.sort_values("score_anomalia", ascending=False)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fav_path = output_dir / "ranking_riesgo_favoritismo.csv"
    frac_path = output_dir / "ranking_riesgo_fraccionamiento.csv"
    ranking_fav.to_csv(fav_path, index=False)
    ranking_frac.to_csv(frac_path, index=False)

    # Segunda verificación después del scoring: inference no debe modificar champions.
    integrity_after = {
        nombre: sha256_archivo(spec["path"]) == spec["sha256"]
        for nombre, spec in registry["artifacts"].items()
    }
    if not all(integrity_after.values()):
        raise RuntimeError("Un artefacto champion cambió durante inference; ejecución abortada.")

    summary = {
        "schema_version": 1,
        "mode": "inference",
        "source_type": integration_summary["source_type"],
        "champion_id": registry["champion_id"],
        "institutional_approval": registry["promotion"]["institutional_approval"],
        "contracts_rows": int(len(contracts)),
        "favoritismo_scored_rows": int(len(ranking_fav)),
        "fraccionamiento_scored_rows": int(len(ranking_frac)),
        "labels_consumed": False,
        "training_invoked": False,
        "tuning_invoked": False,
        "champion_integrity_verified": bool(all(integrity_after.values())),
        "id_funcionario_source_column_present": funcionario_col_presente,
        "id_funcionario_missing_input_rows": funcionarios_nulos_entrada,
        "detail_outputs": {
            "favoritismo": fav_path.as_posix(),
            "fraccionamiento": frac_path.as_posix(),
        },
        "notice": "Scores de priorización del PoC; no constituyen hallazgos de control ni decisión jurídica.",
    }
    if summary_path is None:
        summary_path = output_dir / "inference_summary.json"
    guardar_json_determinista(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description="Puntúa contratos actuales usando el champion; no entrena.")
    parser.add_argument("--config", default="config/local.yaml")
    parser.add_argument("--registry", default="outputs/model_registry.json")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--summary", default=None)
    args = parser.parse_args()
    ejecutar_inference(args.config, args.registry, args.output_dir, args.summary)


if __name__ == "__main__":
    main()
