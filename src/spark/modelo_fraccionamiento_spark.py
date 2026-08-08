"""
Modelo de posible Fraccionamiento con Apache Spark MLlib.

MLlib no incluye Isolation Forest nativo; la ruta objetivo usa KMeans + distancia
al centroide y una señal temporal interpretable. Sprint 3 separa FIT de scoring:
StandardScalerModel y KMeansModel se ajustan únicamente en TRAIN, se persisten
por separado y luego pueden cargarse para INFERENCE sin labels.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

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
OUTPUT_RANKING = Path("outputs/ranking_riesgo_fraccionamiento_spark.csv")
OUTPUT_RESUMEN = Path("outputs/spark_fraccionamiento_resumen.json")
MODEL_DIR = Path(os.environ.get(
    "CGR_SPARK_FRACCIONAMIENTO_MODEL_DIR",
    "outputs/runtime/modelo_fraccionamiento_spark_kmeans",
))
SCALER_DIR = Path(os.environ.get(
    "CGR_SPARK_FRACCIONAMIENTO_SCALER_DIR",
    "outputs/runtime/modelo_fraccionamiento_spark_scaler",
))


def crear_sesion(app_name: str = "cgr-fraccionamiento-poc"):
    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def construir_features_ventana_desde_df(
    df,
    label_col: str | None = "es_fraccionamiento_real",
):
    requeridas = {
        "id_proveedor", "id_entidad", "objeto", "categoria_principal", "fecha_contrato",
        "monto", "id_contrato",
    }
    if label_col is not None:
        requeridas.add(label_col)
    faltantes = requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"Datos Spark no contienen columnas requeridas: {sorted(faltantes)}")

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

    expresiones = [
        F.count("id_contrato").alias("n_contratos_grupo"),
        F.max("contratos_ventana_15d").alias("max_contratos_ventana_15d"),
        F.max("monto_ventana_15d").alias("monto_total_ventana_15d"),
        F.avg("bajo_umbral").alias("pct_montos_bajo_umbral"),
        F.sum("monto").alias("monto_total_grupo"),
    ]
    if label_col is not None:
        expresiones.append(F.max(F.col(label_col).cast("int")).alias("label"))

    grupos = df.groupBy("id_proveedor", "id_entidad", "objeto").agg(*expresiones)
    return grupos.filter(F.col("n_contratos_grupo") >= 2)


def construir_features_ventana(spark):
    df = spark.read.csv("lakehouse/plata/contratos_procesados.csv", header=True, inferSchema=True)
    return construir_features_ventana_desde_df(df)


def aplicar_senal_interpretable(df):
    return df.withColumn(
        "senal_priorizacion_fraccionamiento",
        (F.col("max_contratos_ventana_15d") >= 3)
        & (F.col("pct_montos_bajo_umbral") >= 0.7),
    )


def _agregar_score_distancia(df_pred, modelo):
    centros = modelo.clusterCenters()

    def distancia_centroide(vec, cluster):
        import numpy as np
        return float(np.linalg.norm(np.asarray(vec) - np.asarray(centros[cluster])))

    return df_pred.withColumn(
        "score_anomalia",
        F.udf(distancia_centroide, "double")(F.col("features"), F.col("cluster")),
    )


def entrenar_modelos_kmeans(df, k=2):
    """FIT exclusivo de TRAIN: assembler -> scaler.fit -> kmeans.fit."""
    assembler = VectorAssembler(inputCols=FEATURES, outputCol="features_raw")
    df_vec = assembler.transform(df)
    scaler_model = StandardScaler(
        inputCol="features_raw", outputCol="features", withMean=True, withStd=True
    ).fit(df_vec)
    df_scaled = scaler_model.transform(df_vec)
    modelo = KMeans(featuresCol="features", predictionCol="cluster", k=k, seed=42).fit(df_scaled)
    return _agregar_score_distancia(modelo.transform(df_scaled), modelo), modelo, scaler_model


def puntuar_con_modelos(df, modelo, scaler_model):
    """TRANSFORM puro: no contiene ningún fit."""
    assembler = VectorAssembler(inputCols=FEATURES, outputCol="features_raw")
    df_vec = assembler.transform(df)
    df_scaled = scaler_model.transform(df_vec)
    return _agregar_score_distancia(modelo.transform(df_scaled), modelo)


def detectar_anomalias_kmeans(df, k=2):
    """Alias de compatibilidad para la corrida reproducible."""
    return entrenar_modelos_kmeans(df, k=k)


def validar_sanity(df_pred):
    n_total = df_pred.count()
    n_pos = df_pred.filter(F.col("label") == 1).count()
    top_aciertos = None
    if n_pos:
        top = df_pred.orderBy(F.desc("score_anomalia")).limit(n_pos).toPandas()
        top_aciertos = int(top["label"].sum())
        print(f"Sanity KMeans top-{n_pos}: {top_aciertos}/{n_pos} casos sembrados.")
    marcados = df_pred.filter(F.col("senal_priorizacion_fraccionamiento"))
    n_marcados = marcados.count()
    n_marcados_pos = marcados.filter(F.col("label") == 1).count()
    print(
        f"Sanity señal interpretable: {n_marcados} grupos marcados; "
        f"{n_marcados_pos} sembrados."
    )
    return {
        "n_grupos": int(n_total),
        "positivos_sinteticos": int(n_pos),
        "top_k_aciertos": top_aciertos,
        "senal_interpretable_marcados": int(n_marcados),
        "senal_interpretable_positivos": int(n_marcados_pos),
    }


def guardar_resumen(modelo, sanity, duracion_s):
    resumen = {
        "motor": "Apache Spark MLlib",
        "modo": "local[*]",
        "implementacion_objetivo_tdr": True,
        "dataset": "lakehouse/plata/contratos_procesados.csv",
        "algoritmo": "StandardScaler + KMeans + distancia al centroide",
        "k": int(modelo.getK()),
        "features": FEATURES,
        "sanity_sintetico": sanity,
        "ranking": str(OUTPUT_RANKING),
        "modelo_runtime": str(MODEL_DIR),
        "scaler_runtime": str(SCALER_DIR),
        "duracion_s": round(float(duracion_s), 3),
        "advertencia": (
            "Sanity check sobre benchmark sintético; no estima desempeño productivo. "
            "Ejecución Spark real local; clúster CGR pendiente."
        ),
    }
    OUTPUT_RESUMEN.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_RESUMEN.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumen


def main():
    t0 = time.time()
    spark = crear_sesion()
    spark.sparkContext.setLogLevel("ERROR")
    spark.sparkContext.addPyFile(
        os.path.join(os.path.dirname(__file__), "..", "umbrales_normativos.py")
    )
    try:
        features = aplicar_senal_interpretable(construir_features_ventana(spark))
        pred, modelo, scaler_model = entrenar_modelos_kmeans(features)
        sanity = validar_sanity(pred)

        ranking = pred.select(
            "id_proveedor", "id_entidad", "objeto", "max_contratos_ventana_15d",
            "pct_montos_bajo_umbral", "score_anomalia",
            "senal_priorizacion_fraccionamiento", "label",
        ).orderBy(F.desc("score_anomalia"))
        OUTPUT_RANKING.parent.mkdir(parents=True, exist_ok=True)
        ranking.toPandas().to_csv(OUTPUT_RANKING, index=False)
        MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
        modelo.write().overwrite().save(str(MODEL_DIR))
        scaler_model.write().overwrite().save(str(SCALER_DIR))
        guardar_resumen(modelo, sanity, time.time() - t0)
        print(f"Spark MLlib verificado en entorno local en {time.time()-t0:.1f}s; clúster CGR pendiente.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
