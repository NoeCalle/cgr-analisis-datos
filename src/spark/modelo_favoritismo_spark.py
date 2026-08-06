"""
Modelo de Favoritismo con Apache Spark MLlib (pyspark.ml) — versión que
cierra la brecha señalada frente al TDR: el prototipo original (src/) usa
scikit-learn por velocidad de desarrollo; esta versión corre el mismo
pipeline sobre pyspark.ml.classification.RandomForestClassifier en modo
local, que es la ruta directa hacia el despliegue sobre el Lakehouse
Hadoop de la CGR (Anexo 2 del TDR).

Diferencias reales frente a producción (documentadas, no ocultas):
  - Corre en modo local[*] (una sola máquina), no sobre un clúster YARN.
  - Lee un CSV local, no el Lakehouse (capas Bronce/Plata/Oro).
  - La validación es sobre datos sintéticos, igual que el resto del prototipo.
Todo lo demás — la API de MLlib, VectorAssembler, RandomForestClassifier,
el manejo de pesos de clase — es exactamente lo que correría en producción.
"""

import time
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.ml.feature import VectorAssembler, StringIndexer, OneHotEncoder
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator

FEATURES = [
    "n_contratos", "monto_total", "monto_promedio", "n_objetos_unicos",
    "pct_no_competitiva", "n_funcionarios_distintos", "dias_actividad",
    "concentracion_objeto", "contratos_por_mes", "monto_por_funcionario",
]
MODALIDADES_NO_COMPETITIVAS = ["Contratación Directa", "Comparación de Precios"]


def crear_sesion():
    return (
        SparkSession.builder
        .appName("cgr-modulo-favoritismo")
        .master("local[*]")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "4")  # dataset pequeño, no necesita 200 particiones por defecto
        .getOrCreate()
    )


def cargar_y_limpiar(spark):
    df = spark.read.csv("data/contratos_siaf_seace.csv", header=True, inferSchema=True)

    # Imputación: monto -> mediana por objeto (equivalente a groupby().transform() en pandas,
    # aquí vía percentile_approx + join, que es la forma idiomática en Spark SQL)
    medianas = df.groupBy("objeto").agg(F.expr("percentile_approx(monto, 0.5)").alias("mediana_objeto"))
    mediana_global = df.select(F.expr("percentile_approx(monto, 0.5)").alias("m")).first()["m"]

    df = df.join(medianas, on="objeto", how="left")
    df = df.withColumn("monto", F.coalesce(F.col("monto"), F.col("mediana_objeto"), F.lit(mediana_global)))
    df = df.drop("mediana_objeto")

    for col in ["modalidad", "objeto"]:
        moda = df.groupBy(col).count().orderBy(F.desc("count")).first()[col]
        df = df.withColumn(col, F.coalesce(F.col(col), F.lit(moda)))

    df = df.withColumn(
        "es_modalidad_no_competitiva",
        F.col("modalidad").isin(MODALIDADES_NO_COMPETITIVAS).cast("int"),
    )
    return df


def construir_features_favoritismo(df):
    """Agregación a nivel proveedor+entidad — equivalente Spark del
    groupby().agg() de pandas en src/preprocesamiento.py."""
    agg = df.groupBy("id_proveedor", "id_entidad").agg(
        F.count("id_contrato").alias("n_contratos"),
        F.sum("monto").alias("monto_total"),
        F.avg("monto").alias("monto_promedio"),
        F.countDistinct("objeto").alias("n_objetos_unicos"),
        F.avg("es_modalidad_no_competitiva").alias("pct_no_competitiva"),
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
    """Random Forest de pyspark.ml.classification — misma arquitectura que
    la versión scikit-learn (300 árboles, profundidad 6), con ponderación
    manual de clases (Spark MLlib no tiene class_weight='balanced' nativo
    como scikit-learn; se simula con una columna de pesos, que es el
    patrón estándar en MLlib)."""
    n_pos = df_feat.filter(F.col("label") == 1).count()
    n_neg = df_feat.filter(F.col("label") == 0).count()
    n_total = n_pos + n_neg
    print(f"Casos positivos (favoritismo real): {n_pos} / {n_total} ({n_pos/n_total*100:.2f}%)")

    peso_pos = n_total / (2 * n_pos)
    peso_neg = n_total / (2 * n_neg)
    df_feat = df_feat.withColumn(
        "peso", F.when(F.col("label") == 1, F.lit(peso_pos)).otherwise(F.lit(peso_neg))
    )

    assembler = VectorAssembler(inputCols=FEATURES, outputCol="features")
    df_vec = assembler.transform(df_feat)

    rf = RandomForestClassifier(
        featuresCol="features", labelCol="label", weightCol="peso",
        numTrees=300, maxDepth=6, seed=42,
    )
    modelo = rf.fit(df_vec)
    predicciones = modelo.transform(df_vec)
    return modelo, predicciones


def evaluar(predicciones):
    evaluator = BinaryClassificationEvaluator(labelCol="label", rawPredictionCol="probability", metricName="areaUnderROC")
    auc_roc = evaluator.evaluate(predicciones)
    print(f"AUC-ROC (sobre el conjunto de entrenamiento completo, dataset pequeño): {auc_roc:.3f}")
    print("Nota: para una validación cruzada rigurosa en producción, usar "
          "pyspark.ml.tuning.CrossValidator con StratifiedKFold-equivalente "
          "(Spark no tiene stratified K-fold nativo; se implementa vía "
          "sampleBy() por clase antes de construir los folds).")

    extraer_prob_positiva = F.udf(lambda v: float(v[1]), "double")
    ranking = predicciones.withColumn("score_riesgo_favoritismo", extraer_prob_positiva(F.col("probability")))
    ranking = ranking.select(
        "id_proveedor", "id_entidad", "n_contratos", "pct_no_competitiva",
        "score_riesgo_favoritismo", "label",
    ).orderBy(F.desc("score_riesgo_favoritismo"))

    n_reales = predicciones.filter(F.col("label") == 1).count()
    top = ranking.limit(n_reales).toPandas()
    aciertos = int(top["label"].sum())
    print(f"\nDe los {n_reales} casos reales sembrados, {aciertos} aparecen "
          f"dentro del top-{n_reales} del ranking (Spark MLlib).")

    print("\n--- Top 6 por score de riesgo (Spark MLlib) ---")
    print(ranking.limit(6).toPandas().to_string(index=False))
    return ranking


def main():
    t0 = time.time()
    spark = crear_sesion()
    spark.sparkContext.setLogLevel("ERROR")
    print(f"Sesión Spark iniciada en {time.time()-t0:.1f}s (modo local[*])\n")

    df = cargar_y_limpiar(spark)
    df_feat = construir_features_favoritismo(df)
    modelo, predicciones = entrenar(df_feat)
    ranking = evaluar(predicciones)

    ranking.toPandas().to_csv("outputs/ranking_riesgo_favoritismo_spark.csv", index=False)
    modelo.write().overwrite().save("outputs/models/modelo_favoritismo_spark_rf")
    print("\nModelo Spark guardado en outputs/models/modelo_favoritismo_spark_rf/")
    print(f"\nTiempo total (incluye arranque de sesión): {time.time()-t0:.1f}s")

    spark.stop()


if __name__ == "__main__":
    main()
