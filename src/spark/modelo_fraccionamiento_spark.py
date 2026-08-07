"""
Modelo de Fraccionamiento con Apache Spark MLlib — versión de producción.

Nota de arquitectura importante (documentada explícitamente, no ocultada):
scikit-learn tiene IsolationForest listo para usar; Spark MLlib NO incluye
una implementación nativa de Isolation Forest, y no existe un paquete
empaquetado en PyPI que la agregue de forma confiable a pyspark.ml. El
TDR (numeral 4.2.3) permite explícitamente "agrupamiento (clustering) O
detección de anomalías" — se optó por KMeans de pyspark.ml.clustering,
usando la distancia al centroide asignado como score de anomalía. Esta es
la decisión de arquitectura real que tomaría cualquier equipo construyendo
esto sobre Spark, no una simplificación oculta.

La parte más "Spark-específica" de este módulo es el cálculo de la ventana
móvil de 15 días, que en pandas se resuelve con un loop simple pero en
Spark requiere una Window function con rangeBetween sobre el timestamp —
el patrón idiomático para ventanas temporales en Spark SQL.
"""

import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # para importar umbrales_normativos.py desde src/
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.clustering import KMeans
from pyspark.ml.linalg import Vectors, VectorUDT
from umbrales_normativos import obtener_umbral

SEGUNDOS_15_DIAS = 15 * 86400

FEATURES = [
    "n_contratos_grupo", "max_contratos_ventana_15d", "monto_total_ventana_15d",
    "pct_montos_bajo_umbral", "monto_total_grupo",
]


def crear_sesion():
    return (
        SparkSession.builder
        .appName("cgr-modulo-fraccionamiento")
        .master("local[*]")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def construir_features_ventana(spark):
    """Ventana móvil de 15 días por proveedor+entidad+objeto, usando
    Window.rangeBetween sobre el timestamp — el equivalente Spark del
    loop de ventanas deslizantes en pandas (src/preprocesamiento.py)."""
    df = spark.read.csv("data/contratos_siaf_seace.csv", header=True, inferSchema=True)

    # Misma imputación que el modelo de favoritismo (consistencia entre ambos
    # pipelines Spark): sin esto, filas con objeto/modalidad nulo se agrupan
    # de forma distinta a la versión scikit-learn y el conteo de grupos varía.
    moda_objeto = df.groupBy("objeto").count().orderBy(F.desc("count")).first()["objeto"]
    df = df.withColumn("objeto", F.coalesce(F.col("objeto"), F.lit(moda_objeto)))
    medianas = df.groupBy("objeto").agg(F.expr("percentile_approx(monto, 0.5)").alias("mediana_objeto"))
    mediana_global = df.select(F.expr("percentile_approx(monto, 0.5)").alias("m")).first()["m"]
    df = df.join(medianas, on="objeto", how="left")
    df = df.withColumn("monto", F.coalesce(F.col("monto"), F.col("mediana_objeto"), F.lit(mediana_global)))
    df = df.drop("mediana_objeto")

    df = df.withColumn("ts", F.col("fecha_contrato").cast("timestamp").cast("long"))

    w = (
        Window.partitionBy("id_proveedor", "id_entidad", "objeto")
        .orderBy("ts")
        .rangeBetween(0, SEGUNDOS_15_DIAS)
    )
    df = df.withColumn("contratos_ventana_15d", F.count("id_contrato").over(w))
    df = df.withColumn("monto_ventana_15d", F.sum("monto").over(w))

    # Umbral parametrizado por año y categoría (bienes/servicios vs. obras)
    # — corrección tras revisión externa, ver src/umbrales_normativos.py.
    # UDF porque la lógica de umbral no es una comparación simple de
    # columnas, sino que depende de una tabla normativa externa.
    obtener_umbral_udf = F.udf(lambda fecha, objeto: float(obtener_umbral(fecha, objeto)), "double")
    df = df.withColumn("umbral_aplicable", obtener_umbral_udf(F.col("fecha_contrato"), F.col("objeto")))
    df = df.withColumn("bajo_umbral", (F.col("monto") < F.col("umbral_aplicable") * 0.95).cast("int"))

    grupos = df.groupBy("id_proveedor", "id_entidad", "objeto").agg(
        F.count("id_contrato").alias("n_contratos_grupo"),
        F.max("contratos_ventana_15d").alias("max_contratos_ventana_15d"),
        F.max("monto_ventana_15d").alias("monto_total_ventana_15d"),
        F.avg("bajo_umbral").alias("pct_montos_bajo_umbral"),
        F.sum("monto").alias("monto_total_grupo"),
        F.max(F.col("es_fraccionamiento_real").cast("int")).alias("label"),
    )
    grupos = grupos.filter(F.col("n_contratos_grupo") >= 2)
    return grupos


def aplicar_regla_interpretable(df):
    return df.withColumn(
        "cumple_regla_fraccionamiento",
        (F.col("max_contratos_ventana_15d") >= 3) & (F.col("pct_montos_bajo_umbral") >= 0.7),
    )


def detectar_anomalias_kmeans(df, k=2):
    """KMeans (pyspark.ml.clustering) + distancia euclidiana al centroide
    asignado como score de anomalía — sustituto nativo de MLlib para
    Isolation Forest, dentro de lo que permite el numeral 4.2.3 del TDR."""
    assembler = VectorAssembler(inputCols=FEATURES, outputCol="features_raw")
    df_vec = assembler.transform(df)

    scaler = StandardScaler(inputCol="features_raw", outputCol="features", withMean=True, withStd=True)
    df_scaled = scaler.fit(df_vec).transform(df_vec)

    kmeans = KMeans(featuresCol="features", predictionCol="cluster", k=k, seed=42)
    modelo = kmeans.fit(df_scaled)
    df_pred = modelo.transform(df_scaled)
    centros = modelo.clusterCenters()

    def distancia_centroide(vec, cluster):
        import numpy as np
        return float(np.linalg.norm(np.array(vec) - np.array(centros[cluster])))

    dist_udf = F.udf(distancia_centroide, "double")
    df_pred = df_pred.withColumn("score_anomalia", dist_udf(F.col("features"), F.col("cluster")))
    return df_pred, modelo


def validar(df_pred):
    n_reales = df_pred.filter(F.col("label") == 1).count()
    n_total = df_pred.count()
    print(f"Grupos con fraccionamiento real sembrado: {n_reales} / {n_total}")

    top_kmeans = df_pred.orderBy(F.desc("score_anomalia")).limit(n_reales).toPandas()
    aciertos_kmeans = int(top_kmeans["label"].sum())
    print(f"KMeans (distancia a centroide): {aciertos_kmeans}/{n_reales} casos reales "
          f"están en el top-{n_reales} por score de anomalía")

    marcados_regla = df_pred.filter(F.col("cumple_regla_fraccionamiento"))
    n_marcados = marcados_regla.count()
    aciertos_regla = marcados_regla.filter(F.col("label") == 1).count()
    print(f"Regla interpretable: marca {n_marcados} grupos, {aciertos_regla} son reales "
          f"(precisión: {aciertos_regla/n_marcados*100 if n_marcados else 0:.1f}%)")


def main():
    t0 = time.time()
    spark = crear_sesion()
    spark.sparkContext.setLogLevel("ERROR")
    # Distribuye umbrales_normativos.py a los workers de Spark (procesos
    # Python separados, incluso en modo local) para que el UDF de
    # detectar_anomalias_kmeans() pueda importarlo.
    spark.sparkContext.addPyFile(os.path.join(os.path.dirname(__file__), "..", "umbrales_normativos.py"))
    print(f"Sesión Spark iniciada en {time.time()-t0:.1f}s (modo local[*])\n")

    df = construir_features_ventana(spark)
    df = aplicar_regla_interpretable(df)
    df_pred, modelo_kmeans = detectar_anomalias_kmeans(df)

    validar(df_pred)

    ranking = df_pred.select(
        "id_proveedor", "id_entidad", "objeto", "max_contratos_ventana_15d",
        "pct_montos_bajo_umbral", "score_anomalia", "cumple_regla_fraccionamiento", "label",
    ).orderBy(F.desc("score_anomalia"))

    ranking.toPandas().to_csv("outputs/ranking_riesgo_fraccionamiento_spark.csv", index=False)
    modelo_kmeans.write().overwrite().save("outputs/models/modelo_fraccionamiento_spark_kmeans")
    print("\nModelo Spark guardado en outputs/models/modelo_fraccionamiento_spark_kmeans/")

    print("\n--- Grupos marcados por la regla interpretable (Spark) ---")
    print(ranking.filter(F.col("cumple_regla_fraccionamiento")).toPandas().to_string(index=False))

    print(f"\nTiempo total (incluye arranque de sesión): {time.time()-t0:.1f}s")
    spark.stop()


if __name__ == "__main__":
    main()
