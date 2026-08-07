"""
Modelo de Favoritismo con Apache Spark MLlib — PoC local.

Consume `lakehouse/plata/contratos_procesados.csv`, evitando reimplementar una
segunda limpieza paralela a la capa Plata. Contratación Directa y Comparación
de Precios son features separadas. `local[*]` no equivale a despliegue CGR.
"""

import time
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.tuning import CrossValidator, ParamGridBuilder

FEATURES = [
    "n_contratos", "monto_total", "monto_promedio", "n_objetos_unicos",
    "pct_contratacion_directa", "pct_comparacion_precios",
    "n_funcionarios_distintos", "dias_actividad", "concentracion_objeto",
    "contratos_por_mes", "monto_por_funcionario",
]


def crear_sesion():
    return (
        SparkSession.builder.appName("cgr-modulo-favoritismo-poc")
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


def construir_features_favoritismo(df):
    agg = df.groupBy("id_proveedor", "id_entidad").agg(
        F.count("id_contrato").alias("n_contratos"),
        F.sum("monto").alias("monto_total"),
        F.avg("monto").alias("monto_promedio"),
        F.countDistinct("objeto").alias("n_objetos_unicos"),
        F.avg(F.col("es_contratacion_directa").cast("double")).alias("pct_contratacion_directa"),
        F.avg(F.col("es_comparacion_precios").cast("double")).alias("pct_comparacion_precios"),
        F.countDistinct("id_funcionario").alias("n_funcionarios_distintos"),
        F.min("fecha_contrato").alias("fecha_min"),
        F.max("fecha_contrato").alias("fecha_max"),
        F.max(F.col("es_favoritismo_real").cast("int")).alias("label"),
    )
    agg = agg.withColumn("dias_actividad", F.greatest(F.datediff("fecha_max", "fecha_min"), F.lit(1)))
    agg = agg.withColumn("concentracion_objeto", 1 - (F.col("n_objetos_unicos") / F.col("n_contratos")))
    agg = agg.withColumn("contratos_por_mes", F.col("n_contratos") / (F.col("dias_actividad") / 30))
    agg = agg.withColumn(
        "monto_por_funcionario",
        F.col("monto_total") / F.greatest(F.col("n_funcionarios_distintos"), F.lit(1)),
    )
    return agg.drop("fecha_min", "fecha_max")


def entrenar(df_feat):
    n_pos = df_feat.filter(F.col("label") == 1).count()
    n_neg = df_feat.filter(F.col("label") == 0).count()
    n_total = n_pos + n_neg
    peso_pos = n_total / (2 * n_pos)
    peso_neg = n_total / (2 * n_neg)
    df_feat = df_feat.withColumn(
        "peso", F.when(F.col("label") == 1, F.lit(peso_pos)).otherwise(F.lit(peso_neg))
    )

    df_vec = VectorAssembler(inputCols=FEATURES, outputCol="features").transform(df_feat)
    rf = RandomForestClassifier(featuresCol="features", labelCol="label", weightCol="peso", seed=42)
    param_grid = (
        ParamGridBuilder().addGrid(rf.numTrees, [100, 300]).addGrid(rf.maxDepth, [3, 6]).build()
    )
    cv = CrossValidator(
        estimator=rf,
        estimatorParamMaps=param_grid,
        evaluator=BinaryClassificationEvaluator(
            labelCol="label", rawPredictionCol="rawPrediction", metricName="areaUnderPR"
        ),
        numFolds=3,
        seed=42,
        parallelism=2,
    )
    cv_modelo = cv.fit(df_vec)
    modelo = cv_modelo.bestModel
    print(f"Spark MLlib local: numTrees={modelo.getNumTrees}, maxDepth={modelo.getMaxDepth()}")
    return modelo, modelo.transform(df_vec)


def evaluar(predicciones):
    auc_roc = BinaryClassificationEvaluator(
        labelCol="label", rawPredictionCol="probability", metricName="areaUnderROC"
    ).evaluate(predicciones)
    print(f"AUC-ROC in-sample del modelo seleccionado: {auc_roc:.3f}")
    prob_positiva = F.udf(lambda v: float(v[1]), "double")
    return predicciones.withColumn(
        "score_riesgo_favoritismo", prob_positiva(F.col("probability"))
    ).select(
        "id_proveedor", "id_entidad", "n_contratos",
        "pct_contratacion_directa", "pct_comparacion_precios",
        "score_riesgo_favoritismo", "label",
    ).orderBy(F.desc("score_riesgo_favoritismo"))


def main():
    t0 = time.time()
    spark = crear_sesion()
    spark.sparkContext.setLogLevel("ERROR")
    modelo, predicciones = entrenar(construir_features_favoritismo(cargar_plata(spark)))
    evaluar(predicciones).toPandas().to_csv("outputs/ranking_riesgo_favoritismo_spark.csv", index=False)
    modelo.write().overwrite().save("outputs/models/modelo_favoritismo_spark_rf")
    print(f"Spark MLlib verificado en entorno local en {time.time()-t0:.1f}s; clúster CGR pendiente.")
    spark.stop()


if __name__ == "__main__":
    main()
