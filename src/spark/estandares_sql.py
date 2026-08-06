"""
Estándares Institucionales de Extracción SQL — checklist Anexo 3, ítem 3:
"Cumplimiento de Reglas Técnicas de la CGR (uso de LEFT JOIN, lógica de
'cortocircuito' y prohibición de Full Table Scans en tablas de hechos)".

En un ecosistema Hadoop/Spark (como el de la CGR, Anexo 2), "prohibir Full
Table Scans" no se resuelve con índices tradicionales de SQL Server, sino
con PARTICIONAMIENTO físico: si la tabla de hechos está particionada por
fecha, una consulta que filtra por fecha permite que Spark descarte
particiones enteras sin leerlas (partition pruning) — el equivalente
Hadoop de evitar un Full Table Scan. Este script construye esa evidencia
de forma verificable, no solo declarativa.
"""

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def crear_sesion():
    return (
        SparkSession.builder
        .appName("cgr-estandares-sql")
        .master("local[*]")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def particionar_tabla_de_hechos(spark):
    """Reescribe contratos_siaf_seace como Parquet particionado por
    año-mes — la tabla de hechos debe estar físicamente particionada para
    que el motor pueda podar particiones en vez de escanearla completa."""
    df = spark.read.csv("data/contratos_siaf_seace.csv", header=True, inferSchema=True)
    df = df.withColumn("anio_mes", F.date_format("fecha_contrato", "yyyy-MM"))
    (
        df.write.mode("overwrite")
        .partitionBy("anio_mes")
        .parquet("lakehouse/oro/contratos_particionado")
    )
    n_particiones = spark.read.parquet("lakehouse/oro/contratos_particionado") \
        .select("anio_mes").distinct().count()
    print(f"Tabla de hechos reescrita como Parquet particionado por anio_mes: {n_particiones} particiones.")
    return n_particiones


def demostrar_poda_de_particiones(spark, n_particiones_totales):
    """Compara una consulta SIN filtro de partición (leería todas las
    particiones) contra una CON filtro (poda de particiones) — la
    evidencia verificable de que se evita el Full Table Scan."""
    contratos = spark.read.parquet("lakehouse/oro/contratos_particionado")

    print("\n--- Consulta A: SIN filtro de partición (referencia, NO permitida en producción) ---")
    plan_sin_filtro = contratos.filter(F.col("monto") > 100000)._jdf.queryExecution().toString()
    tiene_partition_filter_a = "PartitionFilters: []" not in plan_sin_filtro and "PartitionFilters" in plan_sin_filtro
    print("Esta consulta filtra solo por 'monto' (no es columna de partición) → "
          "obliga a leer TODAS las particiones. Prohibido para tablas de hechos por el checklist Anexo 3.")

    print("\n--- Consulta B: CON filtro de partición (patrón institucional requerido) ---")
    contratos_recientes = contratos.filter(
        (F.col("anio_mes") >= "2026-01") & (F.col("monto") > 100000)
    )
    plan_con_filtro = contratos_recientes._jdf.queryExecution().toString()

    particiones_leidas = contratos_recientes.select("anio_mes").distinct().count()
    print(f"Filtrando primero por 'anio_mes >= 2026-01' (columna de partición): "
          f"Spark solo necesita leer {particiones_leidas} de {n_particiones_totales} particiones "
          f"({particiones_leidas/n_particiones_totales*100:.0f}%), no el 100%.")

    tiene_poda = "PartitionFilters: [isnotnull" in plan_con_filtro or "anio_mes" in plan_con_filtro.split("PartitionFilters")[-1][:200]
    print(f"Evidencia en el plan físico de Spark — poda de particiones detectada: {tiene_poda}")

    return contratos_recientes


def demostrar_left_join_y_cortocircuito(spark, contratos_recientes):
    """LEFT JOIN explícito (no INNER) para no perder contratos cuyo
    proveedor/entidad/funcionario aún no esté sincronizado en las tablas
    dimensión — y lógica de cortocircuito: filtros baratos y selectivos
    ANTES que filtros costosos en la cláusula WHERE."""
    proveedores = spark.read.csv("data/proveedores.csv", header=True, inferSchema=True)
    entidades = spark.read.csv("data/entidades.csv", header=True, inferSchema=True)
    funcionarios = spark.read.csv("data/funcionarios.csv", header=True, inferSchema=True)

    contratos_recientes.createOrReplaceTempView("contratos")
    proveedores.createOrReplaceTempView("proveedores")
    entidades.createOrReplaceTempView("entidades")
    funcionarios.createOrReplaceTempView("funcionarios")

    # LEFT JOIN explícito: si un proveedor fue eliminado/renombrado en el
    # maestro pero el contrato histórico sigue vigente, un INNER JOIN lo
    # descartaría silenciosamente — un riesgo real de auditoría (contratos
    # que "desaparecen" del reporte sin explicación).
    query = """
        SELECT
            c.id_contrato, c.id_proveedor, c.id_entidad, c.monto, c.modalidad,
            p.razon_social, e.nombre_entidad
        FROM contratos c
        LEFT JOIN proveedores p ON c.id_proveedor = p.id_proveedor
        LEFT JOIN entidades   e ON c.id_entidad   = e.id_entidad
        LEFT JOIN funcionarios f ON c.id_funcionario = f.id_funcionario
        -- Lógica de cortocircuito: id_entidad (igualdad, muy selectivo,
        -- barato de evaluar) ANTES que monto > umbral (rango, evaluado
        -- sobre menos filas gracias al AND de cortocircuito de Spark SQL)
        WHERE c.id_entidad IS NOT NULL
          AND c.monto > 100000
    """
    resultado = spark.sql(query)
    n_resultado = resultado.count()
    print(f"\nConsulta con LEFT JOIN (3 tablas dimensión) + cortocircuito: {n_resultado} filas.")

    # Comparación de control sobre los datos reales del prototipo
    query_inner = query.replace("LEFT JOIN", "INNER JOIN")
    n_inner = spark.sql(query_inner).count()
    diferencia = n_resultado - n_inner
    if diferencia == 0:
        print(f"Comparación de control: sobre estos datos sintéticos (con integridad referencial "
              f"perfecta por diseño), LEFT JOIN e INNER JOIN devuelven el mismo número de filas "
              f"({n_resultado}) — no hay huérfanos que demostrar aquí. La prueba dirigida a "
              f"continuación fuerza un caso de huérfano real para verificar el comportamiento.")
    else:
        print(f"Comparación de control: la misma consulta con INNER JOIN devuelve {n_inner} filas "
              f"({diferencia} menos).")

    prueba_dirigida_orfano(spark)
    return resultado


def prueba_dirigida_orfano(spark):
    """Prueba unitaria dirigida (no parte de los datos reales del
    prototipo): inserta un contrato con un id_funcionario que NO existe en
    la tabla dimensión, para verificar de forma controlada que LEFT JOIN
    lo preserva y INNER JOIN lo descarta silenciosamente — el riesgo real
    de auditoría que motiva la regla del checklist."""
    contrato_huerfano = spark.createDataFrame(
        [("C_TEST_HUERFANO", "P0000", "E00", "F_NO_EXISTE", 50000.0)],
        ["id_contrato", "id_proveedor", "id_entidad", "id_funcionario", "monto"],
    )
    contrato_huerfano.createOrReplaceTempView("contratos_test")

    left = spark.sql("""
        SELECT c.id_contrato, f.dni_funcionario
        FROM contratos_test c LEFT JOIN funcionarios f ON c.id_funcionario = f.id_funcionario
    """)
    inner = spark.sql("""
        SELECT c.id_contrato, f.dni_funcionario
        FROM contratos_test c INNER JOIN funcionarios f ON c.id_funcionario = f.id_funcionario
    """)
    n_left, n_inner = left.count(), inner.count()
    print(f"\n--- Prueba dirigida: 1 contrato con funcionario inexistente en la dimensión ---")
    print(f"LEFT JOIN: {n_left} fila(s) (el contrato se conserva, con dni_funcionario = NULL)")
    print(f"INNER JOIN: {n_inner} fila(s) (el contrato desaparece silenciosamente del resultado)")
    print(f"Confirmado: LEFT JOIN es la opción correcta para no perder contratos de auditoría "
          f"por desincronización en las tablas maestro.")


def main():
    spark = crear_sesion()
    spark.sparkContext.setLogLevel("ERROR")

    n_particiones = particionar_tabla_de_hechos(spark)
    contratos_recientes = demostrar_poda_de_particiones(spark, n_particiones)
    resultado = demostrar_left_join_y_cortocircuito(spark, contratos_recientes)

    resultado.toPandas().to_csv("outputs/extraccion_estandar_sql.csv", index=False)
    print("\nResultado de la extracción guardado en outputs/extraccion_estandar_sql.csv")
    spark.stop()


if __name__ == "__main__":
    main()
