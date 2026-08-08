"""
Evaluación de vínculos con Spark GraphFrames — implementación objetivo del PoC.

Usa la misma capa Plata y los mismos datos de contacto sintéticos enriquecidos
por `src/modelo_grafos.py`. Se ejecuta con Spark real en `local[*]`; esto NO es
una verificación en producción ni en un clúster institucional.

Sprint A añade una evidencia JSON versionable para que la ejecución GraphFrames
pueda ser verificada por CI sin depender de logs efímeros.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

JARS = "jars/graphframes-spark4_2_13-0_10_0.jar,jars/graphframes-graphx-spark4_2_13-0_10_0.jar"
PLATA = "lakehouse/plata"
OUTPUT_SOSPECHOSOS = Path("outputs/vinculos_graphframes_sospechosos.csv")
OUTPUT_PAGERANK = Path("outputs/vinculos_graphframes_pagerank.csv")
OUTPUT_RESUMEN = Path("outputs/graphframes_resumen.json")


def crear_sesion():
    return (
        SparkSession.builder.appName("cgr-vinculos-graphframes-poc").master("local[*]")
        .config("spark.jars", JARS)
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def construir_grafo(spark):
    from graphframes import GraphFrame

    contratos = spark.read.csv(f"{PLATA}/contratos_procesados.csv", header=True, inferSchema=True)
    proveedores = spark.read.csv(f"{PLATA}/proveedores_contacto.csv", header=True, inferSchema=True)
    funcionarios = spark.read.csv(f"{PLATA}/funcionarios_contacto.csv", header=True, inferSchema=True)

    vertices = proveedores.select(
        F.col("id_proveedor").alias("id"), F.lit("proveedor").alias("tipo")
    ).unionByName(
        funcionarios.select(F.col("id_funcionario").alias("id"), F.lit("funcionario").alias("tipo"))
    ).dropDuplicates(["id"])

    edges = contratos.groupBy("id_proveedor", "id_funcionario").agg(
        F.count("id_contrato").alias("n_contratos"),
        F.sum("monto").alias("monto_total"),
    ).select(
        F.col("id_proveedor").alias("src"),
        F.col("id_funcionario").alias("dst"),
        "n_contratos", "monto_total",
    )
    return GraphFrame(vertices, edges), proveedores, funcionarios


def detectar_vinculos_sospechosos(g, proveedores, funcionarios):
    tel_prov = proveedores.select(
        F.col("id_proveedor").alias("src"),
        F.col("telefono").alias("tel_prov"),
        F.col("direccion").alias("dir_prov"),
    )
    tel_func = funcionarios.select(
        F.col("id_funcionario").alias("dst"),
        F.col("telefono").alias("tel_func"),
        F.col("direccion").alias("dir_func"),
    )
    return (
        g.edges.join(tel_prov, "src", "left")
        .join(tel_func, "dst", "left")
        .withColumn(
            "senal_vinculo",
            (F.col("tel_prov") == F.col("tel_func")) | (F.col("dir_prov") == F.col("dir_func")),
        )
    )


def main():
    t0 = time.time()
    spark = crear_sesion()
    spark.sparkContext.setLogLevel("ERROR")
    spark.sparkContext.setCheckpointDir("/tmp/graphframes_checkpoints")
    try:
        g, proveedores, funcionarios = construir_grafo(spark)
        n_vertices = g.vertices.count()
        n_edges = g.edges.count()
        print(f"GraphFrames local: {n_vertices} nodos / {n_edges} aristas.")

        marcados = detectar_vinculos_sospechosos(g, proveedores, funcionarios).filter(
            F.col("senal_vinculo")
        )
        n_marcados = marcados.count()
        print(f"Aristas sintéticas marcadas: {n_marcados}")

        resultados_pr = g.pageRank(resetProbability=0.15, maxIter=10)
        top_funcionarios = (
            resultados_pr.vertices.filter(F.col("tipo") == "funcionario")
            .orderBy(F.desc("pagerank"))
            .limit(10)
        )
        componentes = g.connectedComponents()
        n_componentes = componentes.select("component").distinct().count()
        print(f"Componentes conectados: {n_componentes}")

        OUTPUT_SOSPECHOSOS.parent.mkdir(parents=True, exist_ok=True)
        marcados.toPandas().to_csv(OUTPUT_SOSPECHOSOS, index=False)
        top_funcionarios.toPandas().to_csv(OUTPUT_PAGERANK, index=False)

        resumen = {
            "motor": "Apache Spark + GraphFrames",
            "modo": "local[*]",
            "implementacion_objetivo_tdr": True,
            "jars": JARS.split(","),
            "n_vertices": int(n_vertices),
            "n_aristas": int(n_edges),
            "n_senales_vinculo_sinteticas": int(n_marcados),
            "n_componentes_conectados": int(n_componentes),
            "pagerank_top_n": 10,
            "salidas": [str(OUTPUT_SOSPECHOSOS), str(OUTPUT_PAGERANK)],
            "duracion_s": round(float(time.time() - t0), 3),
            "advertencia": "Datos de contacto sintéticos; clúster y fuentes institucionales CGR pendientes.",
        }
        OUTPUT_RESUMEN.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
        print("GRAPHFRAMES VERIFICADO EN ENTORNO LOCAL SPARK; despliegue CGR pendiente.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
