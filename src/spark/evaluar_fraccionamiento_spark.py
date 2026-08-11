"""Tuning y holdout del modelo Spark activo de fraccionamiento.

Evalúa exactamente StandardScalerModel + KMeansModel + distancia al centroide,
que es el algoritmo del serving Spark. Las etiquetas sintéticas se usan solo
para estratificar/evaluar; KMeans se ajusta sin labels. La evidencia registra
el fingerprint del corpus canónico completo para que TRAIN solo consuma tuning
producido sobre el mismo conjunto de datos.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from pyspark.sql import functions as F

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

from core.config import cargar_config
from core.fingerprints import fingerprint_pandas_dataframe
from core.objeto_similarity import firma_objeto
from ingestar_canonico import integrar
from preprocesamiento import aplicar_estado_preprocesamiento, ajustar_estado_preprocesamiento
from spark.modelo_favoritismo_spark import crear_sesion
from spark.modelo_fraccionamiento_spark import (
    FEATURES,
    construir_features_ventana_desde_df,
    entrenar_modelos_kmeans,
    puntuar_con_modelos,
)
from spark.preprocesamiento_serving_spark import pandas_a_spark

CONFIG_PATH = "config/local-training.yaml"
K_VALUES = [2, 3, 4, 5, 6]
HOLDOUT_SIZE = 0.25
VALIDATION_SIZE = 0.30
VALIDATION_SEEDS = [11, 23, 37]


def _metricas(y, scores, pred_binary):
    y = np.asarray(y).astype(int)
    scores = np.asarray(scores, dtype=float)
    pred_binary = np.asarray(pred_binary).astype(int)
    n_pos = int(y.sum())
    recall_at_k = None
    if n_pos:
        idx = np.argsort(-scores)[:n_pos]
        recall_at_k = float(y[idx].sum() / n_pos)
    return {
        "accuracy": float(accuracy_score(y, pred_binary)),
        "auc_roc": float(roc_auc_score(y, scores)),
        "auc_pr": float(average_precision_score(y, scores)),
        "precision": float(precision_score(y, pred_binary, zero_division=0)),
        "recall": float(recall_score(y, pred_binary, zero_division=0)),
        "f1": float(f1_score(y, pred_binary, zero_division=0)),
        "recall_at_k": recall_at_k,
    }


def _split_raw(contracts: pd.DataFrame):
    base = contracts.copy()
    cats = base["categoria_principal"] if "categoria_principal" in base else pd.Series([None] * len(base))
    base["objeto_familia"] = [firma_objeto(o, c) for o, c in zip(base["objeto"], cats)]
    grupos = (
        base.groupby(["id_proveedor", "id_entidad", "objeto_familia"], as_index=False)["label_fraccionamiento"]
        .max()
        .rename(columns={"label_fraccionamiento": "label"})
    )
    y = grupos["label"].astype(int)
    if y.nunique() != 2 or y.value_counts().min() < 6:
        raise ValueError(f"Benchmark fraccionamiento insuficiente: {y.value_counts().to_dict()}")
    dev_groups, holdout_groups = train_test_split(
        grupos,
        test_size=HOLDOUT_SIZE,
        random_state=2026,
        stratify=y,
    )
    dev_keys = set(zip(dev_groups.id_proveedor, dev_groups.id_entidad, dev_groups.objeto_familia))
    test_keys = set(zip(holdout_groups.id_proveedor, holdout_groups.id_entidad, holdout_groups.objeto_familia))
    keys = list(zip(base.id_proveedor, base.id_entidad, base.objeto_familia))
    dev = contracts.loc[[k in dev_keys for k in keys]].copy()
    test = contracts.loc[[k in test_keys for k in keys]].copy()
    return dev, test


def _feature_id_expr():
    return F.concat_ws("§", "id_proveedor", "id_entidad", "objeto_familia")


def _score_df(df, model, scaler):
    scored = puntuar_con_modelos(df, model, scaler).select(
        _feature_id_expr().alias("gid"), "label", "score_anomalia"
    )
    pdf = scored.toPandas()
    # Para evaluación binaria usamos top-K como umbral operacional de ranking;
    # contamination no forma parte del KMeans Spark.
    n_pos = int(pdf["label"].sum())
    pred = np.zeros(len(pdf), dtype=int)
    if n_pos:
        pred[np.argsort(-pdf["score_anomalia"].to_numpy())[:n_pos]] = 1
    return _metricas(pdf["label"], pdf["score_anomalia"], pred)


def evaluar(config_path: str = CONFIG_PATH):
    config = cargar_config(config_path)
    datasets, _ = integrar(config)
    contracts = datasets["contracts"]
    corpus_fingerprint = fingerprint_pandas_dataframe(contracts)
    dev_raw, holdout_raw = _split_raw(contracts)

    estado = ajustar_estado_preprocesamiento(dev_raw)
    dev_proc = aplicar_estado_preprocesamiento(dev_raw, estado)
    holdout_proc = aplicar_estado_preprocesamiento(holdout_raw, estado)

    spark = crear_sesion("cgr-evaluacion-fraccionamiento-spark", operational=True)
    spark.sparkContext.setLogLevel("ERROR")
    spark.sparkContext.addPyFile(str(SRC_DIR / "core" / "objeto_similarity.py"))
    spark.sparkContext.addPyFile(str(SRC_DIR / "umbrales_normativos.py"))
    try:
        dev_feat = construir_features_ventana_desde_df(
            pandas_a_spark(spark, dev_proc), label_col="label_fraccionamiento"
        ).cache()
        holdout_feat = construir_features_ventana_desde_df(
            pandas_a_spark(spark, holdout_proc), label_col="label_fraccionamiento"
        ).cache()

        dev_keys = dev_feat.select(_feature_id_expr().alias("gid"), "label").toPandas()
        filas = []
        for k in K_VALUES:
            aucs, recalls = [], []
            for seed in VALIDATION_SEEDS:
                train_keys, val_keys = train_test_split(
                    dev_keys,
                    test_size=VALIDATION_SIZE,
                    random_state=seed,
                    stratify=dev_keys["label"].astype(int),
                )
                train_ids = train_keys["gid"].tolist()
                val_ids = val_keys["gid"].tolist()
                train_df = dev_feat.withColumn("gid", _feature_id_expr()).filter(F.col("gid").isin(train_ids)).drop("gid")
                val_df = dev_feat.withColumn("gid", _feature_id_expr()).filter(F.col("gid").isin(val_ids)).drop("gid")
                _, model, scaler = entrenar_modelos_kmeans(train_df, k=k)
                m = _score_df(val_df, model, scaler)
                aucs.append(m["auc_pr"])
                recalls.append(m["recall_at_k"] or 0.0)
            filas.append({
                "k": k,
                "auc_pr_validacion_medio": float(np.mean(aucs)),
                "auc_pr_validacion_min": float(np.min(aucs)),
                "auc_pr_validacion_max": float(np.max(aucs)),
                "recall_at_k_validacion_medio": float(np.mean(recalls)),
            })

        tabla = pd.DataFrame(filas).sort_values(
            ["auc_pr_validacion_medio", "recall_at_k_validacion_medio", "k"],
            ascending=[False, False, True],
        )
        tabla.to_csv("outputs/tuning_fraccionamiento_spark_resultados.csv", index=False)
        best_k = int(tabla.iloc[0]["k"])
        _, final_model, final_scaler = entrenar_modelos_kmeans(dev_feat, k=best_k)
        holdout_metrics = _score_df(holdout_feat, final_model, final_scaler)

        resumen = {
            "schema_version": 2,
            "algorithm": "StandardScalerModel + KMeansModel + distancia al centroide",
            "pipeline": "spark_operational_features",
            "features": FEATURES,
            "training_data_fingerprint_sha256": corpus_fingerprint,
            "design": "holdout final por proveedor-entidad-familia reservado antes del FIT del preprocesador; validación repetida solo en desarrollo",
            "selection_metric": "AUC-PR media de ranking",
            "k_values": K_VALUES,
            "n_desarrollo": int(dev_feat.count()),
            "positivos_desarrollo": int(dev_feat.filter(F.col("label") == 1).count()),
            "n_holdout": int(holdout_feat.count()),
            "positivos_holdout": int(holdout_feat.filter(F.col("label") == 1).count()),
            "mejor_configuracion": {
                "k": best_k,
                "auc_pr_validacion_medio": float(tabla.iloc[0]["auc_pr_validacion_medio"]),
                "recall_at_k_validacion_medio": float(tabla.iloc[0]["recall_at_k_validacion_medio"]),
            },
            "metricas_holdout_final": holdout_metrics,
            "preprocessor_fit_scope": "development_only",
            "labels_used_for_fit": False,
            "advertencia": "benchmark sintético; el holdout no se usa para seleccionar k",
        }
        Path("outputs/tuning_fraccionamiento_spark_resumen.json").write_text(
            json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
        return resumen
    finally:
        spark.stop()


if __name__ == "__main__":
    evaluar()
