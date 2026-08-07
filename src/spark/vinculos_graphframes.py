"""
Evaluación de vínculos con Spark GraphFrames — PoC local.

Usa la misma capa Plata y los mismos datos de contacto sintéticos enriquecidos
por `src/modelo_grafos.py`. Se ejecuta con Spark real en `local[*]`; esto NO es
una verificación en producción ni en un clúster institucional.
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

JARS = "jars/graphframes-spark4_2_13-0_10_0.jar,jars/graphframes-graphx-spark4_2_13-0_10_0.jar"
PLATA = "lakehouse/plata"


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
    )

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
            "vinculo_sospechoso",
            (F.col("tel_prov") == F.col("tel_func")) | (F.col("dir_prov") == F.col("dir_func")),
        )
    )


def main():
    spark = crear_sesion()
    spark.sparkContext.setLogLevel("ERROR")
    spark.sparkContext.setCheckpointDir("/tmp/graphframes_checkpoints")

    g, proveedores, funcionarios = construir_grafo(spark)
    print(f"GraphFrames local: {g.vertices.count()} nodos / {g.edges.count()} aristas.")

    sospechosos = detectar_vinculos_sospechosos(g, proveedores, funcionarios).filter(
        F.col("vinculo_sospechoso")
    )
    print(f"Aristas sintéticas marcadas: {sospechosos.count()}")

    resultados_pr = g.pageRank(resetProbability=0.15, maxIter=10)
    top_funcionarios = (
        resultados_pr.vertices.filter(F.col("tipo") == "funcionario")
        .orderBy(F.desc("pagerank"))
        .limit(10)
    )
    componentes = g.connectedComponents()
    print(f"Componentes conectados: {componentes.select('component').distinct().count()}")

    sospechosos.toPandas().to_csv("outputs/vinculos_graphframes_sospechosos.csv", index=False)
    top_funcionarios.toPandas().to_csv("outputs/vinculos_graphframes_pagerank.csv", index=False)
    print("GRAPHFRAMES VERIFICADO EN ENTORNO LOCAL SPARK; despliegue CGR pendiente.")
    spark.stop()


if __name__ == "__main__":
    main()
