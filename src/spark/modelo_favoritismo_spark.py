"""
Modelo de Favoritismo con Apache Spark MLlib.

Corre en modo local[*] como PoC y mantiene las mismas features conceptuales
que la versión scikit-learn. Desde P1, Contratación Directa y Comparación de
Precios se modelan por separado.
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
        SparkSession.builder
        .appName("cgr-modulo-favoritismo")
        .master("local[*]")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def cargar_y_limpiar(spark):
    df = spark.read.csv("data/contratos_siaf_seace.csv", header=True, inferSchema=True)

    medianas = df.groupBy("objeto").agg(F.expr("percentile_approx(monto, 0.5)").alias("mediana_objeto"))
    mediana_global = df.select(F.expr("percentile_approx(monto, 0.5)").alias("m")).first()["m"]
    df = df.join(medianas, on="objeto", how="left")
    df = df.withColumn("monto", F.coalesce(F.col("monto"), F.col("mediana_objeto"), F.lit(mediana_global)))
    df = df.drop("mediana_objeto")

    for col in ["modalidad", "objeto"]:
        moda = df.groupBy(col).count().orderBy(F.desc("count")).first()[col]
        df = df.withColumn(col, F.coalesce(F.col(col), F.lit(moda)))

    df = df.withColumn("es_contratacion_directa", (F.col("modalidad") == "Contratación Directa").cast("int"))
    df = df.withColumn("es_comparacion_precios", (F.col("modalidad") == "Comparación de Precios").cast("int"))
    return df


def construir_features_favoritismo(df):
    agg = df.groupBy("id_proveedor", "id_entidad").agg(
        F.count("id_contrato").alias("n_contratos"),
        F.sum("monto").alias("monto_total"),
        F.avg("monto").alias("monto_promedio"),
        F.countDistinct("objeto").alias("n_objetos_unicos"),
        F.avg("es_contratacion_directa").alias("pct_contratacion_directa"),
        F.avg("es_comparacion_precios").alias("pct_comparacion_precios"),
        F.countDistinct("id_funcionario").alias("n_funcionarios_distintos"),
        F.min("fecha_contrato").alias("fecha_min"),
        F.max("fecha_contrato").alias("fecha_max"),
        F.max(F.col("es_favoritismo_real").cast("int")).alias("label"),
    )
    agg = agg.withColumn("dias_actividad", F.greatest(F.datediff("fecha_max", "fecha_min"), F.lit(1)))
    agg = agg.withColumn("concentracion_objeto", 1 - (F.col("n_objetos_unicos") / F.col("n_contratos")))
    agg = agg.withColumn("contratos_por_mes", F.col("n_contratos") / (F.col("dias_actividad") / 30))
    agg = agg.withColumn("monto_por_funcionario", F.col("monto_total") / F.col("n_funcionarios_distintos"))
    return agg.drop("fecha_min", "fecha_max")


def entrenar(df_feat):
    n_pos = df_feat.filter(F.col("label") == 1).count()
    n_neg = df_feat.filter(F.col("label") == 0).count()
    n_total = n_pos + n_neg
    print(f"Casos positivos sembrados: {n_pos} / {n_total} ({n_pos/n_total*100:.2f}%)")

    peso_pos = n_total / (2 * n_pos)
    peso_neg = n_total / (2 * n_neg)
    df_feat = df_feat.withColumn(
        "peso", F.when(F.col("label") == 1, F.lit(peso_pos)).otherwise(F.lit(peso_neg))
    )

    assembler = VectorAssembler(inputCols=FEATURES, outputCol="features")
    df_vec = assembler.transform(df_feat)
    rf = RandomForestClassifier(featuresCol="features", labelCol="label", weightCol="peso", seed=42)

    param_grid = (
        ParamGridBuilder()
        .addGrid(rf.numTrees, [100, 300])
        .addGrid(rf.maxDepth, [3, 6])
        .build()
    )
    evaluator = BinaryClassificationEvaluator(
        labelCol="label", rawPredictionCol="rawPrediction", metricName="areaUnderPR"
    )
    cv = CrossValidator(
        estimator=rf, estimatorParamMaps=param_grid, evaluator=evaluator,
        numFolds=3, seed=42, parallelism=2,
    )

    print(f"Búsqueda: {len(param_grid)} combinaciones x 3 folds")
    cv_modelo = cv.fit(df_vec)
    modelo = cv_modelo.bestModel
    print(f"Mejores hiperparámetros: numTrees={modelo.getNumTrees}, maxDepth={modelo.getMaxDepth()}")
    print(f"AUC-PR promedio: {[round(m, 4) for m in cv_modelo.avgMetrics]}")
    return modelo, modelo.transform(df_vec)


def evaluar(predicciones):
    evaluator = BinaryClassificationEvaluator(
        labelCol="label", rawPredictionCol="probability", metricName="areaUnderROC"
    )
    auc_roc = evaluator.evaluate(predicciones)
    print(f"AUC-ROC: {auc_roc:.3f}")

    extraer_prob_positiva = F.udf(lambda v: float(v[1]), "double")
    ranking = predicciones.withColumn(
        "score_riesgo_favoritismo", extraer_prob_positiva(F.col("probability"))
    ).select(
        "id_proveedor", "id_entidad", "n_contratos",
        "pct_contratacion_directa", "pct_comparacion_precios",
        "score_riesgo_favoritismo", "label",
    ).orderBy(F.desc("score_riesgo_favoritismo"))
    return ranking


def main():
    t0 = time.time()
    spark = crear_sesion()
    spark.sparkContext.setLogLevel("ERROR")
    print(f"Sesión Spark iniciada en {time.time()-t0:.1f}s\n")

    df_feat = construir_features_favoritismo(cargar_y_limpiar(spark))
    modelo, predicciones = entrenar(df_feat)
    ranking = evaluar(predicciones)
    ranking.toPandas().to_csv("outputs/ranking_riesgo_favoritismo_spark.csv", index=False)
    modelo.write().overwrite().save("outputs/models/modelo_favoritismo_spark_rf")
    print(f"Tiempo total: {time.time()-t0:.1f}s")
    spark.stop()


if __name__ == "__main__":
    main()
