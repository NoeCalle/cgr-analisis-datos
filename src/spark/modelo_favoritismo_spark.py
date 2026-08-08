"""
Modelo de Favoritismo con Apache Spark MLlib — implementación objetivo del PoC.

Consume la capa Plata para la corrida reproducible. Sprint 3 reutiliza el mismo
feature engineering en serving. Sprint 4 parametriza la columna monetaria:
legacy conserva ``monto`` y TRAIN/INFERENCE operacional usan ``monto_capped``.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

FEATURES = [
    "n_contratos", "monto_total", "monto_promedio", "n_objetos_unicos",
    "pct_contratacion_directa", "pct_comparacion_precios",
    "n_funcionarios_distintos", "dias_actividad", "concentracion_objeto",
    "contratos_por_mes", "monto_por_funcionario",
]
OUTPUT_RANKING = Path("outputs/ranking_riesgo_favoritismo_spark.csv")
OUTPUT_RESUMEN = Path("outputs/spark_favoritismo_resumen.json")
MODEL_DIR = Path(os.environ.get(
    "CGR_SPARK_FAVORITISMO_MODEL_DIR",
    "outputs/runtime/modelo_favoritismo_spark_rf",
))
N_FOLDS = 3


def crear_sesion(app_name: str = "cgr-modulo-favoritismo-poc"):
    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def cargar_plata(spark):
    df = spark.read.csv("lakehouse/plata/contratos_procesados.csv", header=True, inferSchema=True)
    requeridas = {"es_contratacion_directa", "es_comparacion_precios"}
    faltantes = requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"Plata no contiene features esperadas: {sorted(faltantes)}")
    return df


def construir_features_favoritismo(
    df,
    label_col: str | None = "es_favoritismo_real",
    monto_col: str = "monto",
):
    if monto_col not in df.columns:
        raise ValueError(f"Columna de monto Spark para favoritismo no existe: {monto_col!r}")
    expresiones = [
        F.count("id_contrato").alias("n_contratos"),
        F.sum(monto_col).alias("monto_total"),
        F.avg(monto_col).alias("monto_promedio"),
        F.countDistinct("objeto").alias("n_objetos_unicos"),
        F.avg(F.col("es_contratacion_directa").cast("double")).alias("pct_contratacion_directa"),
        F.avg(F.col("es_comparacion_precios").cast("double")).alias("pct_comparacion_precios"),
        F.countDistinct("id_funcionario").alias("n_funcionarios_distintos"),
        F.min("fecha_contrato").alias("fecha_min"),
        F.max("fecha_contrato").alias("fecha_max"),
    ]
    if label_col is not None:
        if label_col not in df.columns:
            raise ValueError(f"Label Spark de favoritismo no existe: {label_col}")
        expresiones.append(F.max(F.col(label_col).cast("int")).alias("label"))

    agg = df.groupBy("id_proveedor", "id_entidad").agg(*expresiones)
    agg = agg.withColumn("dias_actividad", F.greatest(F.datediff("fecha_max", "fecha_min"), F.lit(1)))
    agg = agg.withColumn("concentracion_objeto", 1 - (F.col("n_objetos_unicos") / F.col("n_contratos")))
    agg = agg.withColumn("contratos_por_mes", F.col("n_contratos") / (F.col("dias_actividad") / 30))
    agg = agg.withColumn(
        "monto_por_funcionario",
        F.col("monto_total") / F.greatest(F.col("n_funcionarios_distintos"), F.lit(1)),
    )
    return agg.drop("fecha_min", "fecha_max")


def vectorizar(df_feat):
    return VectorAssembler(inputCols=FEATURES, outputCol="features").transform(df_feat)


def _agregar_folds_estratificados(df_vec):
    orden_hash = F.xxhash64(
        F.col("id_proveedor"), F.col("id_entidad"), F.lit("cgr-sprint-a-folds-v2")
    )
    w = Window.partitionBy("label").orderBy(orden_hash)
    return (
        df_vec.withColumn("_rn_label", F.row_number().over(w) - F.lit(1))
        .withColumn("fold", F.pmod(F.col("_rn_label"), F.lit(N_FOLDS)).cast("int"))
        .drop("_rn_label")
    )


def entrenar(df_feat):
    if "label" not in df_feat.columns:
        raise ValueError("TRAIN Spark de favoritismo requiere label.")
    n_pos = df_feat.filter(F.col("label") == 1).count()
    n_neg = df_feat.filter(F.col("label") == 0).count()
    if n_pos < N_FOLDS or n_neg < N_FOLDS:
        raise ValueError(
            f"No hay ejemplos suficientes para {N_FOLDS} folds: positivos={n_pos}, negativos={n_neg}."
        )
    n_total = n_pos + n_neg
    peso_pos = n_total / (2 * n_pos)
    peso_neg = n_total / (2 * n_neg)
    df_feat = df_feat.withColumn(
        "peso", F.when(F.col("label") == 1, F.lit(peso_pos)).otherwise(F.lit(peso_neg))
    )

    df_vec = _agregar_folds_estratificados(vectorizar(df_feat))
    rf = RandomForestClassifier(featuresCol="features", labelCol="label", weightCol="peso", seed=42)
    param_grid = (
        ParamGridBuilder().addGrid(rf.numTrees, [100, 300]).addGrid(rf.maxDepth, [3, 6]).build()
    )
    evaluador = BinaryClassificationEvaluator(
        labelCol="label", rawPredictionCol="rawPrediction", metricName="areaUnderPR"
    )
    cv = CrossValidator(
        estimator=rf,
        estimatorParamMaps=param_grid,
        evaluator=evaluador,
        numFolds=N_FOLDS,
        foldCol="fold",
        seed=42,
        parallelism=2,
    )
    cv_modelo = cv.fit(df_vec)
    modelo = cv_modelo.bestModel
    mejor_idx = max(range(len(cv_modelo.avgMetrics)), key=cv_modelo.avgMetrics.__getitem__)
    mejor_auc_pr = float(cv_modelo.avgMetrics[mejor_idx])
    print(
        f"Spark MLlib local: numTrees={modelo.getNumTrees}, "
        f"maxDepth={modelo.getMaxDepth()}, AUC-PR CV={mejor_auc_pr:.3f}"
    )
    return modelo, modelo.transform(df_vec), mejor_auc_pr, n_pos, n_total


def generar_ranking(predicciones, include_label: bool = True):
    prob_positiva = F.udf(lambda v: float(v[1]), "double")
    cols = [
        "id_proveedor", "id_entidad", "n_contratos",
        "pct_contratacion_directa", "pct_comparacion_precios",
        "score_riesgo_favoritismo",
    ]
    if include_label and "label" in predicciones.columns:
        cols.append("label")
    return predicciones.withColumn(
        "score_riesgo_favoritismo", prob_positiva(F.col("probability"))
    ).select(*cols).orderBy(F.desc("score_riesgo_favoritismo"))


def guardar_resumen(modelo, auc_pr_cv, n_pos, n_total, duracion_s):
    resumen = {
        "motor": "Apache Spark MLlib",
        "modo": "local[*]",
        "implementacion_objetivo_tdr": True,
        "dataset": "lakehouse/plata/contratos_procesados.csv",
        "algoritmo": "RandomForestClassifier",
        "metrica_seleccion": "AUC-PR CV",
        "cv": f"{N_FOLDS}-fold estratificado con orden xxhash64 determinístico",
        "n_registros": int(n_total),
        "positivos": int(n_pos),
        "mejor_configuracion": {
            "numTrees": int(modelo.getNumTrees),
            "maxDepth": int(modelo.getMaxDepth()),
        },
        "auc_pr_cv": auc_pr_cv,
        "features": FEATURES,
        "amount_source": "monto",
        "ranking": str(OUTPUT_RANKING),
        "modelo_runtime": str(MODEL_DIR),
        "duracion_s": round(float(duracion_s), 3),
        "advertencia": (
            "Benchmark sintético con solo 6 positivos: la métrica CV es de alta varianza y no se usa "
            "como estimación de desempeño productivo. Ejecución Spark real local; clúster CGR pendiente."
        ),
    }
    OUTPUT_RESUMEN.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_RESUMEN.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumen


def main():
    t0 = time.time()
    spark = crear_sesion()
    spark.sparkContext.setLogLevel("ERROR")
    try:
        # Ruta legacy: monto bruto/imputado para reproducir las métricas históricas.
        modelo, predicciones, auc_pr_cv, n_pos, n_total = entrenar(
            construir_features_favoritismo(cargar_plata(spark))
        )
        OUTPUT_RANKING.parent.mkdir(parents=True, exist_ok=True)
        generar_ranking(predicciones).toPandas().to_csv(OUTPUT_RANKING, index=False)
        MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
        modelo.write().overwrite().save(str(MODEL_DIR))
        guardar_resumen(modelo, auc_pr_cv, n_pos, n_total, time.time() - t0)
        print(f"Spark MLlib verificado en entorno local en {time.time()-t0:.1f}s; clúster CGR pendiente.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
