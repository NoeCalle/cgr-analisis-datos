"""Evaluación del RandomForest Spark que corresponde al serving activo.

Reserva un holdout por par proveedor-entidad antes del FIT del preprocesador,
usa ``monto_capped`` y selecciona numTrees/maxDepth únicamente sobre desarrollo.
El holdout final se consulta una sola vez después de elegir hiperparámetros.

Etapa 5B permite ejecutar la evaluación directamente sobre ``spark_sql``: la
integración, el split, el FIT/TRANSFORM y las métricas permanecen en Spark y el
fingerprint es exactamente el mismo contrato distribuido que usa TRAIN.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder
from pyspark.sql import Window
from pyspark.sql import functions as F

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

from core.config import cargar_config
from core.fingerprints import fingerprint_pandas_dataframe, fingerprint_spark_dataframe
from evaluar_favoritismo_operacional import _split_raw_contracts
from ingestar_canonico import integrar, integrar_spark
from preprocesamiento import aplicar_estado_preprocesamiento, ajustar_estado_preprocesamiento
from spark.ajustar_preprocesamiento_spark import ajustar_estado_preprocesamiento_spark
from spark.modelo_favoritismo_spark import FEATURES, construir_features_favoritismo, crear_sesion
from spark.preprocesamiento_serving_spark import aplicar_preprocesamiento_congelado, pandas_a_spark

CONFIG_PATH = "config/local-training.yaml"
AMOUNT_SOURCE = "monto_capped"
SPARK_MEDIANS_PATH = Path("outputs/runtime/evaluation/favoritismo/medianas_monto_por_objeto")


def _metricas_holdout_spark(scored) -> dict:
    """Calcula métricas agregadas sin colectar filas de scoring al driver."""
    tie_expr = (
        F.col("_tie_id").cast("string")
        if "_tie_id" in scored.columns
        else F.monotonically_increasing_id().cast("string")
    )
    prepared = (
        scored.select(
            F.col("label").cast("int").alias("label"),
            F.col("score").cast("double").alias("score"),
            tie_expr.alias("_tie_id"),
        )
        .withColumn("pred", (F.col("score") >= F.lit(0.5)).cast("int"))
        .cache()
    )
    try:
        row = prepared.agg(
            F.count(F.lit(1)).alias("n"),
            F.sum("label").alias("positivos"),
            F.sum(F.when((F.col("label") == 1) & (F.col("pred") == 1), 1).otherwise(0)).alias("tp"),
            F.sum(F.when((F.col("label") == 0) & (F.col("pred") == 1), 1).otherwise(0)).alias("fp"),
            F.sum(F.when((F.col("label") == 0) & (F.col("pred") == 0), 1).otherwise(0)).alias("tn"),
            F.sum(F.when((F.col("label") == 1) & (F.col("pred") == 0), 1).otherwise(0)).alias("fn"),
        ).first()
        n = int(row["n"] or 0)
        n_pos = int(row["positivos"] or 0)
        tp, fp, tn, fn = (int(row[k] or 0) for k in ["tp", "fp", "tn", "fn"])
        if n == 0 or n_pos == 0 or n_pos == n:
            raise ValueError("Holdout Spark requiere ambas clases y al menos una fila.")

        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        accuracy = (tp + tn) / n

        evaluator_pr = BinaryClassificationEvaluator(
            labelCol="label", rawPredictionCol="score", metricName="areaUnderPR"
        )
        evaluator_roc = BinaryClassificationEvaluator(
            labelCol="label", rawPredictionCol="score", metricName="areaUnderROC"
        )
        auc_pr = float(evaluator_pr.evaluate(prepared))
        auc_roc = float(evaluator_roc.evaluate(prepared))

        top_hits_row = (
            prepared.orderBy(F.desc("score"), F.asc("_tie_id"))
            .limit(n_pos)
            .agg(F.sum("label").alias("hits"))
            .first()
        )
        recall_at_k = float(int(top_hits_row["hits"] or 0) / n_pos)
        return {
            "accuracy": float(accuracy),
            "auc_pr": auc_pr,
            "auc_roc": auc_roc,
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "recall_at_k": recall_at_k,
            "threshold": 0.5,
        }
    finally:
        prepared.unpersist()


def _split_raw_contracts_spark(contracts):
    """Holdout estratificado determinístico por par sin listas en el driver."""
    groups = contracts.groupBy("id_proveedor", "id_entidad").agg(
        F.max(F.col("label_favoritismo").cast("int")).alias("_label_split")
    )
    counts = {int(r["_label_split"]): int(r["count"]) for r in groups.groupBy("_label_split").count().collect()}
    if set(counts) != {0, 1} or min(counts.values()) < 6:
        raise ValueError(f"Benchmark favoritismo Spark insuficiente: {counts}")

    w = Window.partitionBy("_label_split").orderBy(
        F.xxhash64("id_proveedor", "id_entidad", F.lit("cgr-fav-holdout-v2"))
    )
    assigned = (
        groups.withColumn("_rn_split", F.row_number().over(w) - F.lit(1))
        .withColumn("_is_holdout", F.pmod(F.col("_rn_split"), F.lit(4)) == 0)
        .select("id_proveedor", "id_entidad", "_is_holdout")
    )
    keyed = contracts.join(assigned, on=["id_proveedor", "id_entidad"], how="inner")
    dev = keyed.where(~F.col("_is_holdout")).drop("_is_holdout")
    holdout = keyed.where(F.col("_is_holdout")).drop("_is_holdout")
    return dev, holdout


def _preprocesar_spark(dev_raw, holdout_raw):
    estado = ajustar_estado_preprocesamiento_spark(
        dev_raw, medians_output_path=SPARK_MEDIANS_PATH
    )
    medianas_df = dev_raw.sparkSession.read.parquet(str(SPARK_MEDIANS_PATH))
    return (
        aplicar_preprocesamiento_congelado(dev_raw, estado, medianas_df=medianas_df),
        aplicar_preprocesamiento_congelado(holdout_raw, estado, medianas_df=medianas_df),
        estado,
    )


def evaluar(config_path: str = CONFIG_PATH):
    config = cargar_config(config_path)
    source_type = config["source"]["type"]
    spark = crear_sesion("cgr-evaluacion-favoritismo-spark", operational=True)
    spark.sparkContext.setLogLevel("ERROR")
    try:
        if source_type == "spark_sql":
            datasets, integration_summary = integrar_spark(config, spark=spark)
            contracts_spark = datasets["contracts"]
            corpus_fingerprint = fingerprint_spark_dataframe(contracts_spark)
            dev_raw, holdout_raw = _split_raw_contracts_spark(contracts_spark)
            dev_proc, holdout_proc, estado = _preprocesar_spark(dev_raw, holdout_raw)
            input_engine = "spark_native"
        else:
            datasets, integration_summary = integrar(config)
            contracts = datasets["contracts"]
            corpus_fingerprint = fingerprint_pandas_dataframe(contracts)
            dev_raw_pdf, holdout_raw_pdf = _split_raw_contracts(contracts)
            estado = ajustar_estado_preprocesamiento(dev_raw_pdf)
            dev_proc = pandas_a_spark(spark, aplicar_estado_preprocesamiento(dev_raw_pdf, estado))
            holdout_proc = pandas_a_spark(spark, aplicar_estado_preprocesamiento(holdout_raw_pdf, estado))
            input_engine = "pandas_adapter"

        dev = construir_features_favoritismo(
            dev_proc,
            label_col="label_favoritismo",
            monto_col=AMOUNT_SOURCE,
        ).cache()
        holdout = construir_features_favoritismo(
            holdout_proc,
            label_col="label_favoritismo",
            monto_col=AMOUNT_SOURCE,
        ).cache()

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
        order_hash = F.xxhash64("id_proveedor", "id_entidad", F.lit("cgr-fav-op-v2"))
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
        rows = [
            {
                "numTrees": int(params[rf.numTrees]),
                "maxDepth": int(params[rf.maxDepth]),
                "auc_pr_cv": float(score),
            }
            for params, score in zip(grid, cv_model.avgMetrics)
        ]
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
            "label",
            F.concat_ws("§", "id_proveedor", "id_entidad").alias("_tie_id"),
            prob_udf("probability").alias("score"),
        )
        metrics = _metricas_holdout_spark(scored)
        importances = {
            feature: float(value)
            for feature, value in zip(FEATURES, final_model.featureImportances.toArray())
        }
        resumen = {
            "schema_version": 3,
            "algorithm": "RandomForestClassificationModel",
            "pipeline": "spark_operational_features",
            "source_type": source_type,
            "input_engine": input_engine,
            "spark_native_evaluation": source_type == "spark_sql",
            "pandas_materialization": False if source_type == "spark_sql" else True,
            "amount_source": AMOUNT_SOURCE,
            "features": FEATURES,
            "training_data_fingerprint_sha256": corpus_fingerprint,
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
            "preprocessor_fit_engine": estado.get("fit_engine", "pandas"),
            "integration_rows": int(integration_summary["domains"]["contracts"]["rows"]),
            "advertencia": "benchmark sintético/local salvo que la configuración apunte a un corpus institucional; holdout final no usado para tuning",
        }
        Path("outputs/tuning_favoritismo_spark_resumen.json").write_text(
            json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
        return resumen
    finally:
        for name in ["dev", "holdout"]:
            obj = locals().get(name)
            if obj is not None:
                obj.unpersist()
        spark.stop()


if __name__ == "__main__":
    evaluar()
