"""Evaluación del RandomForest Spark que corresponde al serving activo.

Reserva un holdout por par proveedor-entidad antes del FIT del preprocesador,
usa ``monto_capped`` y selecciona numTrees/maxDepth únicamente sobre desarrollo.
El holdout final se consulta una sola vez después de elegir hiperparámetros.
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
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.sql import Window
from pyspark.sql import functions as F

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

from core.config import cargar_config
from evaluar_favoritismo_operacional import _split_raw_contracts
from ingestar_canonico import integrar
from preprocesamiento import aplicar_estado_preprocesamiento, ajustar_estado_preprocesamiento
from spark.modelo_favoritismo_spark import FEATURES, construir_features_favoritismo, crear_sesion
from spark.preprocesamiento_serving_spark import pandas_a_spark

CONFIG_PATH = "config/local-training.yaml"
AMOUNT_SOURCE = "monto_capped"


def _metricas_holdout(pdf: pd.DataFrame) -> dict:
    y = pdf["label"].astype(int).to_numpy()
    proba = pdf["score"].to_numpy(dtype=float)
    pred = (proba >= 0.5).astype(int)
    n_pos = int(y.sum())
    recall_at_k = None
    if n_pos:
        recall_at_k = float(y[np.argsort(-proba)[:n_pos]].sum() / n_pos)
    return {
        "accuracy": float(accuracy_score(y, pred)),
        "auc_pr": float(average_precision_score(y, proba)),
        "auc_roc": float(roc_auc_score(y, proba)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "recall_at_k": recall_at_k,
        "threshold": 0.5,
    }


def evaluar(config_path: str = CONFIG_PATH):
    config = cargar_config(config_path)
    datasets, _ = integrar(config)
    contracts = datasets["contracts"]
    dev_raw, holdout_raw = _split_raw_contracts(contracts)
    estado = ajustar_estado_preprocesamiento(dev_raw)
    dev_proc = aplicar_estado_preprocesamiento(dev_raw, estado)
    holdout_proc = aplicar_estado_preprocesamiento(holdout_raw, estado)

    spark = crear_sesion("cgr-evaluacion-favoritismo-spark", operational=True)
    spark.sparkContext.setLogLevel("ERROR")
    try:
        dev = construir_features_favoritismo(
            pandas_a_spark(spark, dev_proc),
            label_col="label_favoritismo",
            monto_col=AMOUNT_SOURCE,
        )
        holdout = construir_features_favoritismo(
            pandas_a_spark(spark, holdout_proc),
            label_col="label_favoritismo",
            monto_col=AMOUNT_SOURCE,
        )

        n_pos = int(dev.filter(F.col("label") == 1).count())
        n_neg = int(dev.filter(F.col("label") == 0).count())
        n_folds = min(5, n_pos, n_neg)
        if n_folds < 3:
            raise ValueError(f"Insuficientes ejemplos para CV Spark: pos={n_pos}, neg={n_neg}")
        n_total = n_pos + n_neg
        weighted = dev.withColumn(
            "peso",
            F.when(F.col("label") == 1, F.lit(n_total / (2 * n_pos))).otherwise(
                F.lit(n_total / (2 * n_neg))
            ),
        )
        order_hash = F.xxhash64("id_proveedor", "id_entidad", F.lit("cgr-fav-op-v1"))
        w = Window.partitionBy("label").orderBy(order_hash)
        folded = (
            weighted.withColumn("_rn", F.row_number().over(w) - 1)
            .withColumn("fold", F.pmod(F.col("_rn"), F.lit(n_folds)).cast("int"))
            .drop("_rn")
        )
        assembled = VectorAssembler(inputCols=FEATURES, outputCol="features").transform(folded)
        rf = RandomForestClassifier(
            featuresCol="features", labelCol="label", weightCol="peso", seed=42
        )
        grid = (
            ParamGridBuilder()
            .addGrid(rf.numTrees, [100, 200, 300])
            .addGrid(rf.maxDepth, [3, 4, 6])
            .build()
        )
        evaluator = BinaryClassificationEvaluator(
            labelCol="label", rawPredictionCol="rawPrediction", metricName="areaUnderPR"
        )
        cv = CrossValidator(
            estimator=rf,
            estimatorParamMaps=grid,
            evaluator=evaluator,
            numFolds=n_folds,
            foldCol="fold",
            seed=42,
            parallelism=2,
        )
        cv_model = cv.fit(assembled)
        best = cv_model.bestModel
        rows = []
        for params, score in zip(grid, cv_model.avgMetrics):
            rows.append({
                "numTrees": int(params[rf.numTrees]),
                "maxDepth": int(params[rf.maxDepth]),
                "auc_pr_cv": float(score),
            })
        pd.DataFrame(rows).sort_values("auc_pr_cv", ascending=False).to_csv(
            "outputs/tuning_favoritismo_spark_resultados.csv", index=False
        )

        final_rf = RandomForestClassifier(
            featuresCol="features",
            labelCol="label",
            weightCol="peso",
            seed=42,
            numTrees=int(best.getNumTrees),
            maxDepth=int(best.getMaxDepth()),
        )
        final_model = final_rf.fit(VectorAssembler(inputCols=FEATURES, outputCol="features").transform(weighted))
        holdout_vec = VectorAssembler(inputCols=FEATURES, outputCol="features").transform(holdout)
        prob_udf = F.udf(lambda v: float(v[1]), "double")
        scored = final_model.transform(holdout_vec).select(
            "label", prob_udf("probability").alias("score")
        ).toPandas()
        metrics = _metricas_holdout(scored)
        importances = {
            feature: float(value)
            for feature, value in zip(FEATURES, final_model.featureImportances.toArray())
        }
        resumen = {
            "schema_version": 1,
            "algorithm": "RandomForestClassificationModel",
            "pipeline": "spark_operational_features",
            "amount_source": AMOUNT_SOURCE,
            "features": FEATURES,
            "design": "holdout final por proveedor-entidad reservado antes del FIT del preprocesador",
            "cv": f"{n_folds}-fold estratificado determinístico solo en desarrollo",
            "n_desarrollo": int(dev.count()),
            "positivos_desarrollo": n_pos,
            "n_holdout": int(holdout.count()),
            "positivos_holdout": int(holdout.filter(F.col("label") == 1).count()),
            "mejor_configuracion": {
                "numTrees": int(final_model.getNumTrees),
                "maxDepth": int(final_model.getMaxDepth()),
                "auc_pr_cv": float(max(cv_model.avgMetrics)),
            },
            "metricas_holdout_final": metrics,
            "feature_importances": importances,
            "preprocessor_fit_scope": "development_only",
            "advertencia": "benchmark sintético; holdout final no usado para tuning",
        }
        Path("outputs/tuning_favoritismo_spark_resumen.json").write_text(
            json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
        return resumen
    finally:
        spark.stop()


if __name__ == "__main__":
    evaluar()
