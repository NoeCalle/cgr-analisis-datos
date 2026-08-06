"""
Demostración de HMS (Hive Metastore Service) — componente del Anexo 2 del
TDR ("HMS MySQL" sobre el Delta Lake).

Registra los datasets reales del prototipo como tablas catalogadas en un
Hive Metastore, permitiendo consultarlas por nombre vía SQL sin conocer
la ruta física del archivo — el propósito real de un metastore: separar
"qué tabla es" de "dónde vive el archivo".

Nota de arquitectura: aquí el metastore corre embebido con Apache Derby
(el backend por defecto de Spark para HMS local), no MySQL como especifica
el Anexo 2. El servicio (catálogo, bases de datos, tablas, SQL sobre
ellas) es el mismo; solo cambia el motor de base de datos que almacena
los metadatos del catálogo — cambiar de Derby a MySQL es una línea de
configuración (spark.hadoop.javax.jdo.option.ConnectionURL), no un
cambio de arquitectura.
"""

from pyspark.sql import SparkSession


def main():
    spark = (
        SparkSession.builder.appName("cgr-hms-demo").master("local[*]")
        .config("spark.sql.warehouse.dir", "outputs/hms_warehouse")
        .enableHiveSupport()
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    spark.sql("CREATE DATABASE IF NOT EXISTS modulo_1_8_2")
    spark.sql("USE modulo_1_8_2")

    # Registrar las tablas reales del prototipo en el catálogo HMS
    tablas = {
        "contratos_siaf_seace": "data/contratos_siaf_seace.csv",
        "dataset_favoritismo": "data/dataset_favoritismo.csv",
        "dataset_fraccionamiento": "data/dataset_fraccionamiento.csv",
        "contratos_reales_seace": "data_real/contratos_reales.csv",
    }
    for nombre, ruta in tablas.items():
        df = spark.read.csv(ruta, header=True, inferSchema=True)
        df.write.mode("overwrite").saveAsTable(nombre)
        print(f"Tabla '{nombre}' registrada en HMS ({df.count():,} filas) desde {ruta}")

    print("\n--- Catálogo HMS: bases de datos ---")
    spark.sql("SHOW DATABASES").show()

    print("--- Catálogo HMS: tablas en modulo_1_8_2 ---")
    spark.sql("SHOW TABLES").show()

    print("--- Consulta SQL directa por nombre de tabla (sin ruta de archivo) ---")
    spark.sql("""
        SELECT id_entidad, COUNT(*) as n_contratos, ROUND(SUM(monto),2) as monto_total
        FROM contratos_siaf_seace
        GROUP BY id_entidad
        ORDER BY monto_total DESC
        LIMIT 5
    """).show()

    print("HMS VERIFICADO: tablas consultables por nombre vía catálogo, sin conocer la ruta física.")
    spark.stop()


if __name__ == "__main__":
    main()
