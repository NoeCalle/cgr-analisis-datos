"""
Estándares de extracción SQL — checklist Anexo 3, ítem 3 del TDR.

Demuestra en el PoC tres principios:
1) LEFT JOIN para preservar hechos aunque falte una dimensión;
2) filtros de partición para habilitar partition pruning y evitar lecturas
   completas de la tabla de hechos cuando el caso de uso lo permita;
3) filtros selectivos aplicados antes de joins/operaciones costosas en el plan
   lógico/físico.

Nota técnica: SQL/Spark NO garantiza evaluación izquierda-a-derecha de los
predicados `AND`. Por eso este módulo no atribuye el rendimiento a un supuesto
"short-circuit" sintáctico. Si el término institucional "cortocircuito" tiene
una definición interna específica, deberá aplicarse literalmente al migrar a
la plataforma CGR.
"""

from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

PLATA = Path("lakehouse/plata")
HECHOS_PARTICIONADOS = PLATA / "contratos_particionado"


def crear_sesion():
    return (
        SparkSession.builder.appName("cgr-estandares-sql-poc")
        .master("local[*]")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def particionar_tabla_de_hechos(spark):
    """Materializa la tabla Plata por año-mes para demostrar pruning."""
    df = spark.read.csv(str(PLATA / "contratos_procesados.csv"), header=True, inferSchema=True)
    df = df.withColumn("anio_mes", F.date_format("fecha_contrato", "yyyy-MM"))
    df.write.mode("overwrite").partitionBy("anio_mes").parquet(str(HECHOS_PARTICIONADOS))
    n = spark.read.parquet(str(HECHOS_PARTICIONADOS)).select("anio_mes").distinct().count()
    print(f"Tabla de hechos Plata particionada: {n} particiones año-mes.")
    return n


def demostrar_poda_de_particiones(spark, n_particiones_totales):
    contratos = spark.read.parquet(str(HECHOS_PARTICIONADOS))

    plan_sin = contratos.filter(F.col("monto") > 100000)._jdf.queryExecution().toString()
    sin_partition_filters = "PartitionFilters: []" in plan_sin
    print(f"Referencia sin filtro de partición -> PartitionFilters vacío: {sin_partition_filters}")

    # Seleccionamos los seis meses más recientes presentes en los datos, sin
    # codificar un año específico que pueda quedar obsoleto.
    meses = [
        r["anio_mes"]
        for r in contratos.select("anio_mes").distinct().orderBy(F.desc("anio_mes")).limit(6).collect()
    ]
    if not meses:
        raise ValueError("No hay particiones anio_mes disponibles.")
    mes_min = min(meses)
    recientes = contratos.filter(
        (F.col("anio_mes") >= F.lit(mes_min)) & (F.col("monto") > F.lit(100000))
    )
    plan_con = recientes._jdf.queryExecution().toString()
    n_leidas = recientes.select("anio_mes").distinct().count()
    tiene_poda = "PartitionFilters" in plan_con and "anio_mes" in plan_con.split("PartitionFilters")[-1][:500]

    print(
        f"Con filtro anio_mes >= {mes_min}: {n_leidas}/{n_particiones_totales} particiones con datos; "
        f"partition pruning visible en plan: {tiene_poda}."
    )
    return recientes, tiene_poda


def demostrar_left_join(spark, contratos_filtrados):
    proveedores = spark.read.csv(str(PLATA / "proveedores.csv"), header=True, inferSchema=True)
    entidades = spark.read.csv(str(PLATA / "entidades.csv"), header=True, inferSchema=True)
    funcionarios = spark.read.csv(str(PLATA / "funcionarios.csv"), header=True, inferSchema=True)

    contratos_filtrados.createOrReplaceTempView("contratos_filtrados")
    proveedores.createOrReplaceTempView("proveedores")
    entidades.createOrReplaceTempView("entidades")
    funcionarios.createOrReplaceTempView("funcionarios")

    # El filtrado temporal y de monto ya ocurrió ANTES de los joins. Esto sí es
    # explícito y verificable, a diferencia de asumir orden de evaluación de AND.
    query = """
        SELECT
            c.id_contrato, c.id_proveedor, c.id_entidad, c.monto, c.modalidad,
            p.razon_social, e.nombre_entidad
        FROM contratos_filtrados c
        LEFT JOIN proveedores p ON c.id_proveedor = p.id_proveedor
        LEFT JOIN entidades e ON c.id_entidad = e.id_entidad
        LEFT JOIN funcionarios f ON c.id_funcionario = f.id_funcionario
        WHERE c.id_entidad IS NOT NULL
    """
    resultado = spark.sql(query)
    print(f"Resultado con LEFT JOIN sobre hechos ya filtrados: {resultado.count()} filas.")
    prueba_dirigida_orfano(spark)
    return resultado


def prueba_dirigida_orfano(spark):
    contrato = spark.createDataFrame(
        [("C_TEST_HUERFANO", "P0000", "E00", "F_NO_EXISTE", 50000.0)],
        ["id_contrato", "id_proveedor", "id_entidad", "id_funcionario", "monto"],
    )
    contrato.createOrReplaceTempView("contratos_test")
    n_left = spark.sql(
        "SELECT c.id_contrato FROM contratos_test c LEFT JOIN funcionarios f "
        "ON c.id_funcionario=f.id_funcionario"
    ).count()
    n_inner = spark.sql(
        "SELECT c.id_contrato FROM contratos_test c INNER JOIN funcionarios f "
        "ON c.id_funcionario=f.id_funcionario"
    ).count()
    if (n_left, n_inner) != (1, 0):
        raise AssertionError(f"Prueba LEFT JOIN inesperada: left={n_left}, inner={n_inner}")
    print("Prueba dirigida LEFT JOIN: conserva huérfano (1 fila); INNER JOIN lo elimina (0).")


def main():
    spark = crear_sesion()
    spark.sparkContext.setLogLevel("ERROR")
    n_particiones = particionar_tabla_de_hechos(spark)
    filtrados, tiene_poda = demostrar_poda_de_particiones(spark, n_particiones)
    if not tiene_poda:
        raise AssertionError("No se detectó partition pruning en el plan de Spark.")
    resultado = demostrar_left_join(spark, filtrados)
    resultado.toPandas().to_csv("outputs/extraccion_estandar_sql.csv", index=False)
    print("Evidencia SQL PoC generada; definición institucional de 'cortocircuito' queda por validar en CGR.")
    spark.stop()


if __name__ == "__main__":
    main()
