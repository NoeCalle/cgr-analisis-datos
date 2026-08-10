"""Autoevaluación del champion ACTIVO y generación de candidatos sin promoción.

A diferencia del monitor histórico sklearn, este módulo lee el registry, exige
que el perfil activo sea ``spark_mllib`` y calcula deriva/performance sobre el
mismo RandomForestClassificationModel que sirve INFERENCE. Si se supera un gate,
genera un nuevo candidate Spark usando el lote etiquetado, pero nunca lo promueve.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pyspark.ml.classification import RandomForestClassificationModel
from pyspark.sql import functions as F

from autoevaluacion import calcular_psi
from core.config import cargar_config
from ingestar_canonico import integrar
from registro_modelos import SPARK_PROFILE, cargar_registry_champion
from spark.entrenar_candidato_spark import entrenar as entrenar_candidate_spark
from spark.modelo_favoritismo_spark import (
    FEATURES,
    construir_features_favoritismo,
    crear_sesion,
    vectorizar,
)
from spark.preprocesamiento_serving_spark import (
    aplicar_preprocesamiento_congelado,
    pandas_a_spark,
)

UMBRAL_PSI = 0.25
UMBRAL_RECALL_MINIMO = 0.80
FEATURES_PSI = [
    "monto_total",
    "pct_contratacion_directa",
    "pct_comparacion_precios",
    "concentracion_objeto",
]
DEFAULT_OUTPUT = Path("outputs/monitoreo_champion.json")
DEFAULT_LOG = Path("outputs/log_reentrenamiento_champion.csv")


def _feature_pdf(spark, raw: pd.DataFrame, estado: dict, *, require_label: bool):
    procesado = aplicar_preprocesamiento_congelado(
        pandas_a_spark(spark, raw), estado, medianas_df=None
    )
    return construir_features_favoritismo(
        procesado,
        label_col="label_favoritismo" if require_label else None,
        monto_col="monto_capped",
    )


def _recall_at_k(pdf: pd.DataFrame) -> float | None:
    y = pdf["label"].astype(int).to_numpy()
    n_pos = int(y.sum())
    if not n_pos:
        return None
    idx = np.argsort(-pdf["score"].to_numpy())[:n_pos]
    return float(y[idx].sum() / n_pos)


def _evaluar_lote(spark, model, estado, baseline_features, raw_new, escenario):
    feat_new = _feature_pdf(spark, raw_new, estado, require_label=True)
    pred = model.transform(vectorizar(feat_new))
    prob_udf = F.udf(lambda v: float(v[1]), "double")
    scored = pred.select(
        *FEATURES_PSI,
        "label",
        prob_udf("probability").alias("score"),
    ).toPandas()
    baseline = baseline_features.select(*FEATURES_PSI).toPandas()

    psi = {
        feature: float(calcular_psi(baseline[feature].to_numpy(), scored[feature].to_numpy()))
        for feature in FEATURES_PSI
    }
    psi_max = max(psi.values())
    recall = _recall_at_k(scored)
    trigger_drift = psi_max > UMBRAL_PSI
    trigger_recall = recall is not None and recall < UMBRAL_RECALL_MINIMO
    return {
        "escenario": escenario,
        "psi": psi,
        "psi_max": float(psi_max),
        "recall_at_k_champion": recall,
        "trigger_drift": bool(trigger_drift),
        "trigger_recall": bool(trigger_recall),
        "retraining_required": bool(trigger_drift or trigger_recall),
        "scored_groups": int(len(scored)),
        "positivos": int(scored["label"].astype(int).sum()),
    }


def _crear_config_retraining(base_config: dict, contracts_path: Path, target: Path):
    cfg = json.loads(json.dumps(base_config))
    cfg["source"]["type"] = "local_csv"
    cfg["source"].pop("tables", None)
    cfg["source"]["datasets"] = {"contracts": contracts_path.as_posix()}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")


def ejecutar(
    registry_path: str | Path = "outputs/model_registry.json",
    config_path: str | Path = "config/local-training.yaml",
    output_path: str | Path = DEFAULT_OUTPUT,
    log_path: str | Path = DEFAULT_LOG,
):
    registry = cargar_registry_champion(registry_path, profile=SPARK_PROFILE)
    if registry["active_serving_profile"] != SPARK_PROFILE:
        raise ValueError("La autoevaluación debe ejecutar el mismo perfil que serving activo.")

    config = cargar_config(config_path)
    datasets, _ = integrar(config)
    train_raw = datasets["contracts"]
    estado = json.loads(Path(registry["artifacts"]["preprocessor_json"]["path"]).read_text(encoding="utf-8"))

    spark = crear_sesion("cgr-monitoreo-champion-activo", operational=True)
    spark.sparkContext.setLogLevel("ERROR")
    try:
        model = RandomForestClassificationModel.load(
            registry["artifacts"]["favoritismo_model"]["path"]
        )
        baseline_features = _feature_pdf(spark, train_raw, estado, require_label=True).cache()
        resultados = []
        lotes = {}
        for escenario in ["normal", "con_drift"]:
            path = Path(f"data/lote_nuevo_{escenario}.csv")
            raw = pd.read_csv(path, parse_dates=["fecha_contrato"])
            # adaptar nombres del CSV sintético al contrato canónico esperado por el feature builder
            raw = raw.rename(columns={
                "es_favoritismo_real": "label_favoritismo",
                "es_fraccionamiento_real": "label_fraccionamiento",
            })
            lotes[escenario] = raw
            resultados.append(
                _evaluar_lote(spark, model, estado, baseline_features, raw, escenario)
            )
    finally:
        spark.stop()

    # El candidate se genera DESPUÉS de cerrar la sesión usada para puntuar el
    # champion, evitando mezclar el proceso de evaluación con un FIT nuevo.
    base_config = config
    for resultado in resultados:
        resultado["active_profile"] = SPARK_PROFILE
        resultado["champion_id"] = registry["champion_id"]
        resultado["candidate_generated"] = False
        resultado["candidate_id"] = None
        resultado["automatic_promotion"] = False
        if not resultado["retraining_required"]:
            continue

        escenario = resultado["escenario"]
        runtime = Path("outputs/runtime/retraining") / escenario
        runtime.mkdir(parents=True, exist_ok=True)
        combined = pd.concat([train_raw, lotes[escenario]], ignore_index=True)
        contracts_path = runtime / "contracts_training.csv"
        combined.to_csv(contracts_path, index=False)
        cfg_path = runtime / "training.yaml"
        _crear_config_retraining(base_config, contracts_path, cfg_path)
        manifest_path = runtime / "candidate_manifest.json"
        manifest = entrenar_candidate_spark(cfg_path, manifest_path)
        resultado["candidate_generated"] = True
        resultado["candidate_id"] = manifest["candidate_id"]
        resultado["candidate_manifest"] = manifest_path.as_posix()

    payload = {
        "schema_version": 1,
        "active_profile": SPARK_PROFILE,
        "champion_id": registry["champion_id"],
        "champion_framework": registry["models"]["favoritismo"]["framework"],
        "feature_source": "monto_capped + champion preprocessor",
        "gates": {"psi_max": UMBRAL_PSI, "recall_at_k_min": UMBRAL_RECALL_MINIMO},
        "scenarios": resultados,
        "automatic_promotion": False,
        "notice": "Los candidates generados requieren revisión/promoción explícita; no existe autopromoción.",
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    log_rows = []
    for r in resultados:
        log_rows.append({
            "escenario": r["escenario"],
            "active_profile": SPARK_PROFILE,
            "champion_id": registry["champion_id"],
            "psi_monto_total": r["psi"]["monto_total"],
            "psi_pct_contratacion_directa": r["psi"]["pct_contratacion_directa"],
            "psi_pct_comparacion_precios": r["psi"]["pct_comparacion_precios"],
            "psi_concentracion_objeto": r["psi"]["concentracion_objeto"],
            "psi_max": r["psi_max"],
            "recall_at_k_champion": r["recall_at_k_champion"],
            "retraining_required": r["retraining_required"],
            "candidate_generated": r["candidate_generated"],
            "candidate_id": r["candidate_id"],
            "automatic_promotion": False,
        })
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(log_rows).to_csv(log_path, index=False)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main():
    parser = argparse.ArgumentParser(description="Autoevalúa el champion Spark activo del registry.")
    parser.add_argument("--registry", default="outputs/model_registry.json")
    parser.add_argument("--config", default="config/local-training.yaml")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    args = parser.parse_args()
    ejecutar(args.registry, args.config, args.output, args.log)


if __name__ == "__main__":
    main()
