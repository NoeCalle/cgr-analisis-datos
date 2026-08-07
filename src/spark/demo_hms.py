"""
Demostración local de Hive Metastore — componente del Anexo 2 del TDR.

Registra tablas de Plata/Oro en un catálogo Hive embebido para demostrar la
separación entre nombre lógico y ruta física. El backend local es Derby; el
Anexo 2 muestra HMS/MySQL en la plataforma institucional.

Esto valida el patrón de catálogo, NO una instalación equivalente a la CGR.
Migrar a MySQL requiere configuración JDBC, driver, credenciales, permisos,
conectividad, HA/backups y parámetros institucionales; no se presenta como un
simple cambio cosmético.
"""

from pathlib import Path

from pyspark.sql import SparkSession


def main():
    spark = (
        SparkSession.builder.appName("cgr-hms-poc").master("local[*]")
        .config("spark.sql.warehouse.dir", "outputs/hms_warehouse")
        .enableHiveSupport()
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    spark.sql("CREATE DATABASE IF NOT EXISTS modulo_1_8_2")
    spark.sql("USE modulo_1_8_2")

    tablas = {
        "plata_contratos": "lakehouse/plata/contratos_procesados.csv",
        "plata_favoritismo": "lakehouse/plata/dataset_favoritismo.csv",
        "plata_fraccionamiento": "lakehouse/plata/dataset_fraccionamiento.csv",
        "oro_favoritismo": "lakehouse/oro/ranking_riesgo_favoritismo.csv",
        "oro_fraccionamiento": "lakehouse/oro/ranking_riesgo_fraccionamiento.csv",
    }
    registradas = 0
    for nombre, ruta in tablas.items():
        if not Path(ruta).exists():
            print(f"Omitida {nombre}: no existe {ruta}; ejecutar el DAG primero.")
            continue
        df = spark.read.csv(ruta, header=True, inferSchema=True)
        df.write.mode("overwrite").saveAsTable(nombre)
        print(f"{nombre}: {df.count():,} filas catalogadas desde {ruta}")
        registradas += 1

    if not registradas:
        raise FileNotFoundError("No hay tablas Plata/Oro para registrar en HMS.")

    print("\nCatálogo HMS local:")
    spark.sql("SHOW TABLES").show(truncate=False)
    if spark.catalog.tableExists("plata_contratos"):
        spark.sql("""
            SELECT id_entidad, COUNT(*) AS n_contratos, ROUND(SUM(monto),2) AS monto_total
            FROM plata_contratos
            GROUP BY id_entidad
            ORDER BY monto_total DESC
            LIMIT 5
        """).show()

    print("HMS verificado como PoC local con Derby; HMS/MySQL institucional pendiente.")
    spark.stop()


if __name__ == "__main__":
    main()
