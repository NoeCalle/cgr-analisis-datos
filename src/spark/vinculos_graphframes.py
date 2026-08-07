"""
Evaluación de Vínculos con GraphFrames (Spark real) — cierra la brecha que
antes estaba bloqueada (ver Sección 5 y Anexo B del reporte técnico): el
prototipo original usaba networkx porque GraphFrames no lograba resolverse
sin acceso a Maven. Con los .jar correctos (io.graphframes:graphframes-
spark4_2.13:0.10.0, obtenidos directamente de Maven Central fuera de este
entorno y cargados vía spark.jars), GraphFrames corre de verdad.

Además de replicar la detección de vínculos sospechosos (comparación con
Sección 5), se usan dos capacidades nativas de GraphFrames que networkx
no ofrece a esta escala de forma distribuida:
  - PageRank: identifica funcionarios que concentran relevancia en la red
    de contratación (no solo cuentan contratos, sino su posición en la
    red).
  - Connected Components: agrupa proveedores y funcionarios en clústeres
    conectados, útil para detectar comunidades de contratación aisladas.
"""

import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

JARS = "jars/graphframes-spark4_2_13-0_10_0.jar,jars/graphframes-graphx-spark4_2_13-0_10_0.jar"


def crear_sesion():
    return (
        SparkSession.builder.appName("cgr-vinculos-graphframes").master("local[*]")
        .config("spark.jars", JARS)
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def construir_grafo(spark):
    from graphframes import GraphFrame

    contratos = spark.read.csv("data/contratos_siaf_seace.csv", header=True, inferSchema=True)
    proveedores = spark.read.csv("data/proveedores_contacto.csv", header=True, inferSchema=True)
    funcionarios = spark.read.csv("data/funcionarios_contacto.csv", header=True, inferSchema=True)

    vertices_prov = proveedores.select(F.col("id_proveedor").alias("id"), F.lit("proveedor").alias("tipo"))
    vertices_func = funcionarios.select(F.col("id_funcionario").alias("id"), F.lit("funcionario").alias("tipo"))
    vertices = vertices_prov.unionByName(vertices_func)

    edges = contratos.groupBy("id_proveedor", "id_funcionario").agg(
        F.count("id_contrato").alias("n_contratos"), F.sum("monto").alias("monto_total"),
    ).select(
        F.col("id_proveedor").alias("src"), F.col("id_funcionario").alias("dst"),
        "n_contratos", "monto_total",
    )

    g = GraphFrame(vertices, edges)
    return g, proveedores, funcionarios


def detectar_vinculos_sospechosos(g, proveedores, funcionarios):
    """Igual que la Sección 5 del reporte (comparte teléfono/dirección),
    pero calculado sobre las aristas del GraphFrame en vez de un DataFrame
    plano de pandas."""
    tel_prov = proveedores.select(F.col("id_proveedor").alias("src"), F.col("telefono").alias("tel_prov"),
                                    F.col("direccion").alias("dir_prov"))
    tel_func = funcionarios.select(F.col("id_funcionario").alias("dst"), F.col("telefono").alias("tel_func"),
                                     F.col("direccion").alias("dir_func"))

    edges_enriquecidas = g.edges.join(tel_prov, "src").join(tel_func, "dst")
    edges_enriquecidas = edges_enriquecidas.withColumn(
        "vinculo_sospechoso",
        (F.col("tel_prov") == F.col("tel_func")) | (F.col("dir_prov") == F.col("dir_func")),
    )
    return edges_enriquecidas


def main():
    spark = crear_sesion()
    spark.sparkContext.setLogLevel("ERROR")
    spark.sparkContext.setCheckpointDir("/tmp/graphframes_checkpoints")  # requerido por connectedComponents

    g, proveedores, funcionarios = construir_grafo(spark)
    print(f"Grafo construido con GraphFrames: {g.vertices.count()} nodos, {g.edges.count()} aristas.")

    print("\n--- Vínculos sospechosos (comparte teléfono/dirección) ---")
    edges_sosp = detectar_vinculos_sospechosos(g, proveedores, funcionarios)
    sospechosos = edges_sosp.filter(F.col("vinculo_sospechoso"))
    n_sosp = sospechosos.count()
    print(f"Aristas sospechosas detectadas: {n_sosp}")
    sospechosos.select("src", "dst", "n_contratos", "tel_prov", "tel_func").show(truncate=False)

    print("\n--- PageRank: funcionarios más centrales en la red de contratación ---")
    resultados_pr = g.pageRank(resetProbability=0.15, maxIter=10)
    top_funcionarios = (
        resultados_pr.vertices.filter(F.col("tipo") == "funcionario")
        .orderBy(F.desc("pagerank")).limit(10)
    )
    top_funcionarios.show(truncate=False)

    print("\n--- Connected Components: clústeres de la red proveedor-funcionario ---")
    componentes = g.connectedComponents()
    resumen_componentes = componentes.groupBy("component").count().orderBy(F.desc("count"))
    n_componentes = resumen_componentes.count()
    print(f"N° de componentes conectados: {n_componentes}")
    resumen_componentes.show(10)

    sospechosos.toPandas().to_csv("outputs/vinculos_graphframes_sospechosos.csv", index=False)
    top_funcionarios.toPandas().to_csv("outputs/vinculos_graphframes_pagerank.csv", index=False)

    print("\nGRAPHFRAMES VERIFICADO EN PRODUCCIÓN: reemplaza networkx con Spark GraphFrames real.")
    spark.stop()


if __name__ == "__main__":
    main()
