"""Tuning y holdout del modelo Spark activo de fraccionamiento.

Evalúa exactamente StandardScalerModel + KMeansModel + distancia al centroide.
Las etiquetas se usan para estratificar/evaluar; KMeans se ajusta sin labels.

Etapa 5B incorpora una ruta ``spark_sql`` completamente distribuida: split de
holdout, validación repetida, FIT/TRANSFORM y métricas se ejecutan en Spark sin
listas de IDs ni materialización del dataset en pandas.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.sql import Window
from pyspark.sql import functions as F

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

from core.config import cargar_config
from core.fingerprints import fingerprint_pandas_dataframe, fingerprint_spark_dataframe
from core.objeto_similarity import firma_objeto
from ingestar_canonico import integrar, integrar_spark
from preprocesamiento import aplicar_estado_preprocesamiento, ajustar_estado_preprocesamiento
from spark.ajustar_preprocesamiento_spark import ajustar_estado_preprocesamiento_spark
from spark.modelo_favoritismo_spark import crear_sesion
from spark.modelo_fraccionamiento_spark import (
    FEATURES,
    _firma_objeto_spark,
    construir_features_ventana_desde_df,
    entrenar_modelos_kmeans,
    puntuar_con_modelos,
)
from spark.preprocesamiento_serving_spark import aplicar_preprocesamiento_congelado, pandas_a_spark

CONFIG_PATH = "config/local-training.yaml"
K_VALUES = [2, 3, 4, 5, 6]
VALIDATION_SEEDS = [11, 23, 37]
SPARK_MEDIANS_PATH = Path("outputs/runtime/evaluation/fraccionamiento/medianas_monto_por_objeto")


def _feature_id_expr():
    return F.concat_ws("§", "id_proveedor", "id_entidad", "objeto_familia")


def _metricas_spark(scored) -> dict:
    """Métricas de ranking/holdout sin colectar observaciones al driver."""
    prepared = scored.select(
        F.col("label").cast("int").alias("label"),
        F.col("score_anomalia").cast("double").alias("score"),
    ).cache()
    try:
        base = prepared.agg(
            F.count(F.lit(1)).alias("n"),
            F.sum("label").alias("positivos"),
        ).first()
        n = int(base["n"] or 0)
        n_pos = int(base["positivos"] or 0)
        if n == 0 or n_pos == 0 or n_pos == n:
            raise ValueError("Evaluación Spark de fraccionamiento requiere ambas clases.")

        ranking = prepared.withColumn(
            "_rn_score",
            F.row_number().over(Window.orderBy(F.desc("score"), F.desc("label"))),
        ).withColumn("pred", (F.col("_rn_score") <= F.lit(n_pos)).cast("int"))
        row = ranking.agg(
            F.sum(F.when((F.col("label") == 1) & (F.col("pred") == 1), 1).otherwise(0)).alias("tp"),
            F.sum(F.when((F.col("label") == 0) & (F.col("pred") == 1), 1).otherwise(0)).alias("fp"),
            F.sum(F.when((F.col("label") == 0) & (F.col("pred") == 0), 1).otherwise(0)).alias("tn"),
            F.sum(F.when((F.col("label") == 1) & (F.col("pred") == 0), 1).otherwise(0)).alias("fn"),
        ).first()
        tp, fp, tn, fn = (int(row[k] or 0) for k in ["tp", "fp", "tn", "fn"])
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
        accuracy = (tp + tn) / n
        auc_pr = float(BinaryClassificationEvaluator(
            labelCol="label", rawPredictionCol="score", metricName="areaUnderPR"
        ).evaluate(prepared))
        auc_roc = float(BinaryClassificationEvaluator(
            labelCol="label", rawPredictionCol="score", metricName="areaUnderROC"
        ).evaluate(prepared))
        return {
            "accuracy": float(accuracy),
            "auc_roc": auc_roc,
            "auc_pr": auc_pr,
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "recall_at_k": float(recall),
        }
    finally:
        prepared.unpersist()


def _score_metrics(df, model, scaler):
    scored = puntuar_con_modelos(df, model, scaler).select(
        "label", "score_anomalia"
    )
    return _metricas_spark(scored)


def _with_split_family(df):
    categoria = F.col("categoria_principal") if "categoria_principal" in df.columns else F.lit(None)
    return df.withColumn(
        "_objeto_familia_split",
        _firma_objeto_spark(F.col("objeto"), categoria),
    )


def _split_raw_spark(contracts):
    """Holdout 25% estratificado por proveedor-entidad-familia en Spark."""
    base = _with_split_family(contracts)
    groups = base.groupBy(
        "id_proveedor", "id_entidad", "_objeto_familia_split"
    ).agg(F.max(F.col("label_fraccionamiento").cast("int")).alias("_label_split"))
    counts = {int(r["_label_split"]): int(r["count"]) for r in groups.groupBy("_label_split").count().collect()}
    if set(counts) != {0, 1} or min(counts.values()) < 6:
        raise ValueError(f"Benchmark fraccionamiento Spark insuficiente: {counts}")

    w = Window.partitionBy("_label_split").orderBy(
        F.xxhash64(
            "id_proveedor", "id_entidad", "_objeto_familia_split",
            F.lit("cgr-frac-holdout-v2"),
        )
    )
    assigned = (
        groups.withColumn("_rn_split", F.row_number().over(w) - F.lit(1))
        .withColumn("_is_holdout", F.pmod(F.col("_rn_split"), F.lit(4)) == 0)
        .select("id_proveedor", "id_entidad", "_objeto_familia_split", "_is_holdout")
    )
    keyed = base.join(
        assigned,
        on=["id_proveedor", "id_entidad", "_objeto_familia_split"],
        how="inner",
    )
    dev = keyed.where(~F.col("_is_holdout")).drop("_is_holdout", "_objeto_familia_split")
    holdout = keyed.where(F.col("_is_holdout")).drop("_is_holdout", "_objeto_familia_split")
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


def _validation_split_spark(dev_feat, seed: int):
    """Split repetido estratificado sin recolectar IDs ni usar ``isin`` local."""
    with_gid = dev_feat.withColumn("_gid", _feature_id_expr())
    w = Window.partitionBy("label").orderBy(
        F.xxhash64("_gid", F.lit(int(seed)), F.lit("cgr-frac-validation-v2"))
    )
    assigned = (
        with_gid.withColumn("_rn_validation", F.row_number().over(w) - F.lit(1))
        .withColumn("_is_validation", F.pmod(F.col("_rn_validation"), F.lit(3)) == 0)
    )
    train_df = assigned.where(~F.col("_is_validation")).drop(
        "_gid", "_rn_validation", "_is_validation"
    )
    val_df = assigned.where(F.col("_is_validation")).drop(
        "_gid", "_rn_validation", "_is_validation"
    )
    return train_df, val_df


def _split_raw_pandas(contracts: pd.DataFrame):
    """Compatibilidad local: mismo criterio de familia, sin afectar spark_sql."""
    base = contracts.copy()
    cats = base["categoria_principal"] if "categoria_principal" in base else pd.Series([None] * len(base))
    base["_objeto_familia_split"] = [firma_objeto(o, c) for o, c in zip(base["objeto"], cats)]
    groups = (
        base.groupby(["id_proveedor", "id_entidad", "_objeto_familia_split"], as_index=False)["label_fraccionamiento"]
        .max()
        .rename(columns={"label_fraccionamiento": "_label_split"})
    )
    groups = groups.sort_values(
        ["_label_split", "id_proveedor", "id_entidad", "_objeto_familia_split"]
    ).copy()
    groups["_rn"] = groups.groupby("_label_split").cumcount()
    groups["_is_holdout"] = (groups["_rn"] % 4) == 0
    keyed = base.merge(
        groups[["id_proveedor", "id_entidad", "_objeto_familia_split", "_is_holdout"]],
        on=["id_proveedor", "id_entidad", "_objeto_familia_split"],
        how="inner",
    )
    dev = keyed.loc[~keyed["_is_holdout"]].drop(columns=["_is_holdout", "_objeto_familia_split"])
    holdout = keyed.loc[keyed["_is_holdout"]].drop(columns=["_is_holdout", "_objeto_familia_split"])
    return dev, holdout


def evaluar(config_path: str = CONFIG_PATH):
    config = cargar_config(config_path)
    source_type = config["source"]["type"]
    spark = crear_sesion("cgr-evaluacion-fraccionamiento-spark", operational=True)
    spark.sparkContext.setLogLevel("ERROR")
    spark.sparkContext.addPyFile(str(SRC_DIR / "umbrales_normativos.py"))
    try:
        if source_type == "spark_sql":
            datasets, integration_summary = integrar_spark(config, spark=spark)
            contracts_spark = datasets["contracts"]
            corpus_fingerprint = fingerprint_spark_dataframe(contracts_spark)
            dev_raw, holdout_raw = _split_raw_spark(contracts_spark)
            dev_proc, holdout_proc, estado = _preprocesar_spark(dev_raw, holdout_raw)
            input_engine = "spark_native"
        else:
            datasets, integration_summary = integrar(config)
            contracts = datasets["contracts"]
            corpus_fingerprint = fingerprint_pandas_dataframe(contracts)
            dev_pdf, holdout_pdf = _split_raw_pandas(contracts)
            estado = ajustar_estado_preprocesamiento(dev_pdf)
            dev_proc = pandas_a_spark(spark, aplicar_estado_preprocesamiento(dev_pdf, estado))
            holdout_proc = pandas_a_spark(spark, aplicar_estado_preprocesamiento(holdout_pdf, estado))
            input_engine = "pandas_adapter"

        dev_feat = construir_features_ventana_desde_df(
            dev_proc, label_col="label_fraccionamiento"
        ).cache()
        holdout_feat = construir_features_ventana_desde_df(
            holdout_proc, label_col="label_fraccionamiento"
        ).cache()

        counts_dev = {int(r["label"]): int(r["count"]) for r in dev_feat.groupBy("label").count().collect()}
        counts_holdout = {int(r["label"]): int(r["count"]) for r in holdout_feat.groupBy("label").count().collect()}
        if set(counts_dev) != {0, 1} or set(counts_holdout) != {0, 1}:
            raise ValueError(
                f"Split fraccionamiento sin ambas clases: dev={counts_dev}, holdout={counts_holdout}"
            )

        filas = []
        for k in K_VALUES:
            aucs, recalls = [], []
            for seed in VALIDATION_SEEDS:
                train_df, val_df = _validation_split_spark(dev_feat, seed)
                _, model, scaler = entrenar_modelos_kmeans(train_df, k=k)
                metrics = _score_metrics(val_df, model, scaler)
                aucs.append(metrics["auc_pr"])
                recalls.append(metrics["recall_at_k"])
            filas.append({
                "k": k,
                "auc_pr_validacion_medio": float(sum(aucs) / len(aucs)),
                "auc_pr_validacion_min": float(min(aucs)),
                "auc_pr_validacion_max": float(max(aucs)),
                "recall_at_k_validacion_medio": float(sum(recalls) / len(recalls)),
            })

        tabla = pd.DataFrame(filas).sort_values(
            ["auc_pr_validacion_medio", "recall_at_k_validacion_medio", "k"],
            ascending=[False, False, True],
        )
        tabla.to_csv("outputs/tuning_fraccionamiento_spark_resultados.csv", index=False)
        best_k = int(tabla.iloc[0]["k"])
        _, final_model, final_scaler = entrenar_modelos_kmeans(dev_feat, k=best_k)
        holdout_metrics = _score_metrics(holdout_feat, final_model, final_scaler)

        resumen = {
            "schema_version": 3,
            "algorithm": "StandardScalerModel + KMeansModel + distancia al centroide",
            "pipeline": "spark_operational_features",
            "source_type": source_type,
            "input_engine": input_engine,
            "spark_native_evaluation": source_type == "spark_sql",
            "pandas_materialization": False if source_type == "spark_sql" else True,
            "features": FEATURES,
            "training_data_fingerprint_sha256": corpus_fingerprint,
            "design": "holdout final por proveedor-entidad-familia reservado antes del FIT; validación repetida estratificada y distribuida solo en desarrollo",
            "selection_metric": "AUC-PR media de ranking",
            "k_values": K_VALUES,
            "n_desarrollo": int(dev_feat.count()),
            "positivos_desarrollo": int(counts_dev[1]),
            "n_holdout": int(holdout_feat.count()),
            "positivos_holdout": int(counts_holdout[1]),
            "mejor_configuracion": {
                "k": best_k,
                "auc_pr_validacion_medio": float(tabla.iloc[0]["auc_pr_validacion_medio"]),
                "recall_at_k_validacion_medio": float(tabla.iloc[0]["recall_at_k_validacion_medio"]),
            },
            "metricas_holdout_final": holdout_metrics,
            "preprocessor_fit_scope": "development_only",
            "preprocessor_fit_engine": estado.get("fit_engine", "pandas"),
            "labels_used_for_fit": False,
            "integration_rows": int(integration_summary["domains"]["contracts"]["rows"]),
            "advertencia": "benchmark sintético/local salvo que la configuración apunte a un corpus institucional; holdout no usado para seleccionar k",
        }
        Path("outputs/tuning_fraccionamiento_spark_resumen.json").write_text(
            json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(resumen, ensure_ascii=False, indent=2))
        return resumen
    finally:
        for name in ["dev_feat", "holdout_feat"]:
            obj = locals().get(name)
            if obj is not None:
                obj.unpersist()
        spark.stop()


if __name__ == "__main__":
    evaluar()
