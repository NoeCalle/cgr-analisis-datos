"""Modelo de posible fraccionamiento con Apache Spark MLlib.

MLlib no incluye Isolation Forest nativo; la ruta objetivo usa KMeans +
distancia al centroide y una señal temporal interpretable. La semántica de las
features se mantiene alineada con pandas: cantidad y monto pertenecen a la
misma ventana de 15 días y pequeñas variantes lexicales del objeto se agrupan
mediante una firma reproducible y auditable.

La firma ``objeto_familia`` se construye con expresiones Spark SQL nativas; no
usa un UDF Python ni requiere importar módulos del proyecto en cada worker.
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
TUNING_PATH = Path("outputs/tuning_fraccionamiento_spark_resumen.json")
MODEL_DIR = Path(os.environ.get(
    "CGR_SPARK_FRACCIONAMIENTO_MODEL_DIR",
    "outputs/runtime/modelo_fraccionamiento_spark_kmeans",
))
SCALER_DIR = Path(os.environ.get(
    "CGR_SPARK_FRACCIONAMIENTO_SCALER_DIR",
    "outputs/runtime/modelo_fraccionamiento_spark_scaler",
))

STOPWORDS_OBJETO = [
    "de", "del", "la", "las", "el", "los", "y", "e", "para", "por", "con",
    "en", "a", "un", "una", "unos", "unas", "servicio", "servicios",
    "adquisicion", "adquisiciones", "contratacion", "contrataciones",
    "compra", "compras", "obra", "obras", "publica", "publico",
    "preventivo", "preventiva", "preventivos", "preventivas",
    "correctivo", "correctiva", "correctivos", "correctivas",
]
SYNONYMS_OBJETO = {
    "conservacion": "mantenimiento",
    "conservar": "mantenimiento",
    "mantenimientos": "mantenimiento",
    "vias": "via",
    "vial": "via",
    "viales": "via",
    "carretera": "via",
    "carreteras": "via",
    "equipos": "equipo",
    "informaticos": "informatico",
    "informaticas": "informatico",
    "materiales": "material",
}


def crear_sesion(app_name: str = "cgr-fraccionamiento-poc"):
    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def k_seleccionado(default: int = 2) -> tuple[int, str]:
    if not TUNING_PATH.exists():
        return int(default), "poc_default"
    data = json.loads(TUNING_PATH.read_text(encoding="utf-8"))
    k = data.get("mejor_configuracion", {}).get("k")
    if k is None:
        raise ValueError(f"Resumen Spark de fraccionamiento incompleto: {TUNING_PATH}")
    return int(k), "spark_holdout_summary"


def _normalizar_texto_spark(columna):
    texto = F.lower(columna.cast("string"))
    texto = F.translate(texto, "áéíóúüñ", "aeiouun")
    return F.trim(F.regexp_replace(texto, "[^a-z0-9]+", " "))


def _firma_objeto_spark(objeto_col, categoria_col):
    """Equivalente Spark-native de ``core.objeto_similarity.firma_objeto``."""
    stopwords = F.array(*[F.lit(x) for x in STOPWORDS_OBJETO])
    synonym_pairs = []
    for key, value in SYNONYMS_OBJETO.items():
        synonym_pairs.extend([F.lit(key), F.lit(value)])
    synonym_map = F.create_map(*synonym_pairs)

    tokens = F.split(_normalizar_texto_spark(objeto_col), " ")
    tokens = F.filter(
        tokens,
        lambda x: (F.length(x) > 0) & (~F.array_contains(stopwords, x)),
    )
    tokens = F.transform(tokens, lambda x: F.coalesce(F.element_at(synonym_map, x), x))
    tokens = F.filter(tokens, lambda x: ~F.array_contains(stopwords, x))
    tokens = F.array_sort(F.array_distinct(tokens))

    categoria = F.coalesce(_normalizar_texto_spark(categoria_col), F.lit("sin_categoria"))
    return F.when(
        F.size(tokens) > 0,
        F.concat(categoria, F.lit("::"), F.concat_ws("|", tokens)),
    ).otherwise(F.concat(categoria, F.lit("::__SIN_OBJETO__")))


def construir_features_ventana_desde_df(
    df,
    label_col: str | None = "es_fraccionamiento_real",
):
    requeridas = {
        "id_proveedor", "id_entidad", "objeto", "fecha_contrato",
        "monto", "id_contrato",
    }
    if label_col is not None:
        requeridas.add(label_col)
    faltantes = requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"Datos Spark no contienen columnas requeridas: {sorted(faltantes)}")

    categoria_expr = F.col("categoria_principal") if "categoria_principal" in df.columns else F.lit(None)
    obtener_umbral_udf = F.udf(
        lambda fecha, objeto, categoria: float(
            obtener_umbral(fecha, objeto=objeto, categoria_principal=categoria)
        ),
        "double",
    )

    base = (
        df.withColumn(
            "objeto_familia",
            _firma_objeto_spark(F.col("objeto"), categoria_expr),
        )
        .withColumn("ts", F.col("fecha_contrato").cast("timestamp").cast("long"))
    )
    grupo_cols = ["id_proveedor", "id_entidad", "objeto_familia"]
    w15 = (
        Window.partitionBy(*grupo_cols)
        .orderBy("ts")
        .rangeBetween(0, SEGUNDOS_15_DIAS)
    )
    base = (
        base.withColumn("contratos_ventana_15d", F.count("id_contrato").over(w15))
        .withColumn("monto_ventana_15d", F.sum("monto").over(w15))
        .withColumn(
            "umbral_aplicable",
            obtener_umbral_udf(F.col("fecha_contrato"), F.col("objeto"), categoria_expr),
        )
        .withColumn(
            "bajo_umbral",
            (F.col("monto") < F.col("umbral_aplicable") * 0.95).cast("int"),
        )
    )

    # Misma regla que pandas: elegir UNA ventana por máximo número de contratos
    # y, en empate, el inicio cronológicamente más temprano. El monto publicado
    # pertenece exactamente a esa ventana.
    w_pick = Window.partitionBy(*grupo_cols).orderBy(
        F.desc("contratos_ventana_15d"), F.asc("ts"), F.asc("id_contrato")
    )
    mejor_ventana = (
        base.withColumn("_rn_ventana", F.row_number().over(w_pick))
        .filter(F.col("_rn_ventana") == 1)
        .select(
            *grupo_cols,
            F.col("contratos_ventana_15d").alias("max_contratos_ventana_15d"),
            F.col("monto_ventana_15d").alias("monto_total_ventana_15d"),
        )
    )

    expresiones = [
        F.count("id_contrato").alias("n_contratos_grupo"),
        F.avg("bajo_umbral").alias("pct_montos_bajo_umbral"),
        F.sum("monto").alias("monto_total_grupo"),
        F.first("objeto", ignorenulls=True).alias("objeto"),
    ]
    if label_col is not None:
        expresiones.append(F.max(F.col(label_col).cast("int")).alias("label"))

    grupos = base.groupBy(*grupo_cols).agg(*expresiones)
    return (
        grupos.join(mejor_ventana, grupo_cols, "inner")
        .filter(F.col("n_contratos_grupo") >= 2)
    )


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
    modelo = KMeans(featuresCol="features", predictionCol="cluster", k=int(k), seed=42).fit(df_scaled)
    return _agregar_score_distancia(modelo.transform(df_scaled), modelo), modelo, scaler_model


def puntuar_con_modelos(df, modelo, scaler_model):
    """TRANSFORM puro: no contiene ningún fit."""
    assembler = VectorAssembler(inputCols=FEATURES, outputCol="features_raw")
    df_vec = assembler.transform(df)
    df_scaled = scaler_model.transform(df_vec)
    return _agregar_score_distancia(modelo.transform(df_scaled), modelo)


def detectar_anomalias_kmeans(df, k=2):
    return entrenar_modelos_kmeans(df, k=k)


def validar_sanity(df_pred):
    n_total = df_pred.count()
    n_pos = df_pred.filter(F.col("label") == 1).count()
    top_aciertos = None
    if n_pos:
        top = df_pred.orderBy(F.desc("score_anomalia")).limit(n_pos).select("label").collect()
        top_aciertos = int(sum(int(row["label"]) for row in top))
        print(f"Sanity KMeans top-{n_pos}: {top_aciertos}/{n_pos} casos sembrados.")
    marcados = df_pred.filter(F.col("senal_priorizacion_fraccionamiento"))
    n_marcados = marcados.count()
    n_marcados_pos = marcados.filter(F.col("label") == 1).count()
    return {
        "n_grupos": int(n_total),
        "positivos_sinteticos": int(n_pos),
        "top_k_aciertos": top_aciertos,
        "senal_interpretable_marcados": int(n_marcados),
        "senal_interpretable_positivos": int(n_marcados_pos),
    }


def guardar_resumen(modelo, sanity, duracion_s, selection_source):
    resumen = {
        "motor": "Apache Spark MLlib",
        "modo": "local[*]",
        "implementacion_objetivo_tdr": True,
        "dataset": "lakehouse/plata/contratos_procesados.csv",
        "algoritmo": "StandardScaler + KMeans + distancia al centroide",
        "k": int(modelo.getK()),
        "selection_source": selection_source,
        "features": FEATURES,
        "window_semantics": "cantidad y monto de la misma ventana de 15 días; empate por inicio más temprano",
        "object_grouping": "firma lexical reproducible objeto_familia (Spark SQL nativo)",
        "sanity_sintetico": sanity,
        "ranking": str(OUTPUT_RANKING),
        "modelo_runtime": str(MODEL_DIR),
        "scaler_runtime": str(SCALER_DIR),
        "duracion_s": round(float(duracion_s), 3),
        "advertencia": (
            "Sanity check sobre benchmark sintético; la evidencia out-of-sample del KMeans "
            "se publica en tuning_fraccionamiento_spark_resumen.json. No estima desempeño productivo."
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
        k, source = k_seleccionado()
        pred, modelo, scaler_model = entrenar_modelos_kmeans(features, k=k)
        sanity = validar_sanity(pred)

        ranking = pred.select(
            "id_proveedor", "id_entidad", "objeto", "objeto_familia",
            "max_contratos_ventana_15d", "monto_total_ventana_15d",
            "pct_montos_bajo_umbral", "score_anomalia",
            "senal_priorizacion_fraccionamiento", "label",
        ).orderBy(F.desc("score_anomalia"))
        OUTPUT_RANKING.parent.mkdir(parents=True, exist_ok=True)
        ranking.toPandas().to_csv(OUTPUT_RANKING, index=False)
        MODEL_DIR.parent.mkdir(parents=True, exist_ok=True)
        modelo.write().overwrite().save(str(MODEL_DIR))
        scaler_model.write().overwrite().save(str(SCALER_DIR))
        guardar_resumen(modelo, sanity, time.time() - t0, source)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
