"""
Modelo de posible Fraccionamiento con Apache Spark MLlib — PoC local.

El TDR permite clustering o detección de anomalías. MLlib no incluye Isolation
Forest nativo, por lo que este módulo usa KMeans + distancia al centroide como
comparador estadístico y conserva la ventana temporal Spark SQL como evidencia
de implementación distribuible.

P1:
- consume `lakehouse/plata/contratos_procesados.csv`;
- usa `categoria_principal` junto con fecha/objeto en el motor normativo;
- denomina la regla como señal de priorización, no "regla legal";
- las métricas sobre casos sembrados son sanity checks del PoC.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyspark.ml.clustering import KMeans
from pyspark.ml.feature import StandardScaler, VectorAssembler
from pyspark.sql import SparkSession, Window
from pyspark.sql import functions as F

from umbrales_normativos import obtener_umbral

SEGUNDOS_15_DIAS = 15 * 86400
FEATURES = [
    "n_contratos_grupo", "max_contratos_ventana_15d", "monto_total_ventana_15d",
    "pct_montos_bajo_umbral", "monto_total_grupo",
]


def crear_sesion():
    return (
        SparkSession.builder.appName("cgr-fraccionamiento-poc")
        .master("local[*]")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def construir_features_ventana(spark):
    """Construye features desde la capa Plata usando ventanas Spark SQL."""
    df = spark.read.csv("lakehouse/plata/contratos_procesados.csv", header=True, inferSchema=True)
    requeridas = {
        "id_proveedor", "id_entidad", "objeto", "categoria_principal", "fecha_contrato",
        "monto", "id_contrato", "es_fraccionamiento_real",
    }
    faltantes = requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"Plata no contiene columnas requeridas: {sorted(faltantes)}")

    df = df.withColumn("ts", F.col("fecha_contrato").cast("timestamp").cast("long"))
    w = (
        Window.partitionBy("id_proveedor", "id_entidad", "objeto")
        .orderBy("ts")
        .rangeBetween(0, SEGUNDOS_15_DIAS)
    )
    df = df.withColumn("contratos_ventana_15d", F.count("id_contrato").over(w))
    df = df.withColumn("monto_ventana_15d", F.sum("monto").over(w))

    obtener_umbral_udf = F.udf(
        lambda fecha, objeto, categoria: float(
            obtener_umbral(fecha, objeto=objeto, categoria_principal=categoria)
        ),
        "double",
    )
    df = df.withColumn(
        "umbral_aplicable",
        obtener_umbral_udf(F.col("fecha_contrato"), F.col("objeto"), F.col("categoria_principal")),
    )
    df = df.withColumn(
        "bajo_umbral", (F.col("monto") < F.col("umbral_aplicable") * 0.95).cast("int")
    )

    grupos = df.groupBy("id_proveedor", "id_entidad", "objeto").agg(
        F.count("id_contrato").alias("n_contratos_grupo"),
        F.max("contratos_ventana_15d").alias("max_contratos_ventana_15d"),
        F.max("monto_ventana_15d").alias("monto_total_ventana_15d"),
        F.avg("bajo_umbral").alias("pct_montos_bajo_umbral"),
        F.sum("monto").alias("monto_total_grupo"),
        F.max(F.col("es_fraccionamiento_real").cast("int")).alias("label"),
    )
    return grupos.filter(F.col("n_contratos_grupo") >= 2)


def aplicar_senal_interpretable(df):
    return df.withColumn(
        "senal_priorizacion_fraccionamiento",
        (F.col("max_contratos_ventana_15d") >= 3)
        & (F.col("pct_montos_bajo_umbral") >= 0.7),
    )


def detectar_anomalias_kmeans(df, k=2):
    assembler = VectorAssembler(inputCols=FEATURES, outputCol="features_raw")
    df_vec = assembler.transform(df)
    scaler = StandardScaler(
        inputCol="features_raw", outputCol="features", withMean=True, withStd=True
    )
    df_scaled = scaler.fit(df_vec).transform(df_vec)
    modelo = KMeans(featuresCol="features", predictionCol="cluster", k=k, seed=42).fit(df_scaled)
    df_pred = modelo.transform(df_scaled)
    centros = modelo.clusterCenters()

    def distancia_centroide(vec, cluster):
        import numpy as np
        return float(np.linalg.norm(np.asarray(vec) - np.asarray(centros[cluster])))

    return (
        df_pred.withColumn(
            "score_anomalia",
            F.udf(distancia_centroide, "double")(F.col("features"), F.col("cluster")),
        ),
        modelo,
    )


def validar_sanity(df_pred):
    n_pos = df_pred.filter(F.col("label") == 1).count()
    if n_pos:
        top = df_pred.orderBy(F.desc("score_anomalia")).limit(n_pos).toPandas()
        print(f"Sanity KMeans top-{n_pos}: {int(top['label'].sum())}/{n_pos} casos sembrados.")
    marcados = df_pred.filter(F.col("senal_priorizacion_fraccionamiento"))
    print(
        f"Sanity señal interpretable: {marcados.count()} grupos marcados; "
        f"{marcados.filter(F.col('label') == 1).count()} sembrados."
    )


def main():
    t0 = time.time()
    spark = crear_sesion()
    spark.sparkContext.setLogLevel("ERROR")
    spark.sparkContext.addPyFile(
        os.path.join(os.path.dirname(__file__), "..", "umbrales_normativos.py")
    )

    features = aplicar_senal_interpretable(construir_features_ventana(spark))
    pred, modelo = detectar_anomalias_kmeans(features)
    validar_sanity(pred)

    ranking = pred.select(
        "id_proveedor", "id_entidad", "objeto", "max_contratos_ventana_15d",
        "pct_montos_bajo_umbral", "score_anomalia", "senal_priorizacion_fraccionamiento", "label",
    ).orderBy(F.desc("score_anomalia"))
    ranking.toPandas().to_csv("outputs/ranking_riesgo_fraccionamiento_spark.csv", index=False)
    modelo.write().overwrite().save("outputs/models/modelo_fraccionamiento_spark_kmeans")
    print(f"Spark MLlib verificado en entorno local en {time.time()-t0:.1f}s; clúster CGR pendiente.")
    spark.stop()


if __name__ == "__main__":
    main()
