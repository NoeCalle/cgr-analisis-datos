"""Checks de integración reproducible sin depender de conteos históricos rígidos."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    contracts = pd.read_csv("data/contratos_siaf_seace.csv")
    fav = pd.read_csv("lakehouse/plata/dataset_favoritismo.csv")
    frac = pd.read_csv("lakehouse/plata/dataset_fraccionamiento.csv")
    spark_fav = pd.read_csv("outputs/ranking_riesgo_favoritismo_spark.csv")
    spark_frac = pd.read_csv("outputs/ranking_riesgo_fraccionamiento_spark.csv")

    assert len(contracts) >= 4000
    assert int(fav["label_favoritismo_real"].sum()) >= 20
    assert int(frac["label_fraccionamiento_real"].sum()) >= 15
    assert "objeto_familia" in frac.columns
    assert "objeto_familia" in spark_frac.columns
    assert "senal_priorizacion_fraccionamiento" in spark_frac.columns
    assert "pct_no_competitiva" not in spark_fav.columns
    assert "cumple_regla_fraccionamiento" not in spark_frac.columns

    comparacion = load_json("outputs/comparacion_modelos_favoritismo.json")
    fav_tuning = load_json("outputs/tuning_favoritismo_resumen.json")
    fav_spark_tuning = load_json("outputs/tuning_favoritismo_spark_resumen.json")
    frac_spark_tuning = load_json("outputs/tuning_fraccionamiento_spark_resumen.json")
    frac_compat = load_json("outputs/tuning_fraccionamiento_resumen.json")

    assert comparacion["pipeline"] == "operational_frozen_preprocessor"
    assert comparacion["amount_source"] == "monto_capped"
    assert len(comparacion["resultados"]) == 3
    assert fav_tuning["pipeline"] == "operational_frozen_preprocessor"
    assert fav_tuning["amount_source"] == "monto_capped"
    assert fav_tuning["positivos_holdout"] >= 4
    for metric in ["accuracy", "auc_pr", "auc_roc", "precision", "recall", "f1", "recall_at_k"]:
        assert metric in fav_tuning["metricas_holdout_final"]

    assert fav_spark_tuning["pipeline"] == "spark_operational_features"
    assert fav_spark_tuning["amount_source"] == "monto_capped"
    assert fav_spark_tuning["positivos_holdout"] >= 4
    assert fav_spark_tuning["mejor_configuracion"]["numTrees"] in {100, 200, 300}
    assert fav_spark_tuning["mejor_configuracion"]["maxDepth"] in {3, 4, 6}
    assert set(fav_spark_tuning["feature_importances"]) == set(fav_spark_tuning["features"])

    assert frac_spark_tuning["algorithm"].startswith("StandardScalerModel + KMeansModel")
    assert frac_spark_tuning["labels_used_for_fit"] is False
    assert frac_spark_tuning["positivos_holdout"] >= 3
    assert frac_spark_tuning["mejor_configuracion"]["k"] in {2, 3, 4, 5, 6}
    for metric in ["accuracy", "auc_pr", "auc_roc", "precision", "recall", "f1", "recall_at_k"]:
        assert metric in frac_spark_tuning["metricas_holdout_final"]
    # IsolationForest se conserva como benchmark de compatibilidad, no como
    # evidencia del champion Spark.
    assert "metricas_holdout_final" in frac_compat

    registry = load_json("outputs/model_registry.json")
    spark_profile = registry["serving_profiles"]["spark_mllib"]
    assert registry["active_serving_profile"] == "spark_mllib"
    assert spark_profile["models"]["favoritismo"]["amount_source"] == "monto_capped"
    assert spark_profile["models"]["favoritismo"]["params"]["selection_source"] == "spark_operational_holdout"
    assert spark_profile["models"]["fraccionamiento"]["params"]["selection_source"] == "spark_operational_holdout"
    assert set(spark_profile["models"]["favoritismo"]["feature_importances"]) == set(
        spark_profile["models"]["favoritismo"]["features"]
    )

    sklearn_summary = load_json("outputs/inference_smoke_summary.json")
    spark_summary = load_json("outputs/inference_spark_smoke_summary.json")
    assert sklearn_summary["favoritismo_amount_source"] == "monto_capped"
    assert spark_summary["favoritismo_amount_source"] == "monto_capped"
    assert spark_summary["champion_id"] == spark_profile["champion_id"]
    assert spark_summary["labels_consumed"] is False
    assert spark_summary["training_invoked"] is False
    assert spark_summary["tuning_invoked"] is False

    monitor = load_json("outputs/monitoreo_champion.json")
    assert monitor["active_profile"] == "spark_mllib"
    assert monitor["champion_id"] == spark_profile["champion_id"]
    assert monitor["automatic_promotion"] is False
    assert {s["escenario"] for s in monitor["scenarios"]} == {"normal", "con_drift"}
    assert all(s["champion_id"] == spark_profile["champion_id"] for s in monitor["scenarios"])

    pagos = load_json("outputs/analisis_pagos_modalidades.json")
    pagos_csv = pd.read_csv("data/pagos_siaf_sintetico.csv")
    assert pagos["payments"]["orphan_payments"] == 0
    assert pagos["payments"]["contracts_rows"] == len(contracts)
    assert pagos["payments"]["payments_rows"] == len(pagos_csv)

    graphframes = load_json("outputs/graphframes_resumen.json")
    assert graphframes["implementacion_objetivo_tdr"] is True
    assert graphframes["n_vertices"] > 0 and graphframes["n_aristas"] > 0

    manifest = load_json("outputs/run_manifest.json")
    evidencia = load_json("outputs/evidencia_documental.json")
    assert manifest["schema_version"] >= 3
    assert evidencia["run_manifest"]["git_commit"] == manifest["git_commit"]

    diccionario = pd.read_csv("data/diccionario_datos.csv")
    texto_dic = " ".join(diccionario.astype(str).fillna("").values.ravel()).lower()
    for obsoleto in ["pct_no_competitiva", "cumple_regla_fraccionamiento", "s/. 400,000"]:
        assert obsoleto not in texto_dic

    print(
        "Pipeline metodológico 2B OK | "
        f"contratos={len(contracts)} fav+={int(fav['label_favoritismo_real'].sum())} "
        f"frac+={int(frac['label_fraccionamiento_real'].sum())} "
        f"champion={spark_profile['champion_id']}"
    )


if __name__ == "__main__":
    main()
