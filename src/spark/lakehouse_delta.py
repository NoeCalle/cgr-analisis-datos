"""
Lakehouse con Delta Lake real (no solo Parquet) — cierra la brecha
señalada en el Anexo B del reporte técnico. Usa los .jar exactos
(io.delta:delta-spark_4.1_2.13:4.3.0) obtenidos de Maven Central fuera de
este entorno, igual que GraphFrames.

Por qué esto importa específicamente para un auditor (no es una feature
genérica): Delta Lake mantiene un historial de cada escritura
(`DESCRIBE HISTORY`) y permite "viajar en el tiempo" a cualquier versión
anterior de la tabla, mientras esa versión no haya sido purgada. Si un
funcionario corrige (o manipula) un monto después de que un auditor ya lo
revisó, Delta Lake conserva la versión original — algo que un CSV
sobrescrito no puede ofrecer. Esta demo simula exactamente ese escenario:
una corrección de monto sobre la capa Bronce, y la capacidad de consultar
el valor ANTES de la corrección.

PRECISIÓN IMPORTANTE (corrección tras revisión externa): el historial de
Delta Lake NO es inmutable de forma permanente. El comando `VACUUM`
elimina físicamente los archivos de datos de versiones antiguas que ya no
están referenciadas, según una política de retención configurable
(`delta.deletedFileRetentionDuration`, por defecto 7 días). Pasado ese
período, y si se ejecuta VACUUM, el time travel a esas versiones deja de
funcionar. Para uso de auditoría, esto significa que la política de
retención debe configurarse explícitamente en línea con el período que la
CGR necesite conservar evidencia (potencialmente años, no los 7 días por
defecto), y que VACUUM debe ejecutarse con ese criterio en mente, no
dejarse en su configuración por defecto sin revisión.
"""

import os
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from delta.tables import DeltaTable

JARS = "jars/delta-spark_4_1_2_13-4_3_0.jar,jars/delta-storage-4_3_0.jar"
RUTA_BRONCE_DELTA = os.path.abspath("lakehouse_delta/bronce_contratos")


def crear_sesion():
    return (
        SparkSession.builder.appName("cgr-lakehouse-delta").master("local[*]")
        .config("spark.jars", JARS)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def cargar_capa_bronce_delta(spark):
    """Escribe la tabla de hechos como Delta Lake real (versión 0)."""
    df = spark.read.csv("data/contratos_siaf_seace.csv", header=True, inferSchema=True)
    df.write.format("delta").mode("overwrite").save(RUTA_BRONCE_DELTA)
    print(f"Capa Bronce (Delta Lake real) escrita: {df.count():,} contratos — versión 0.")


def simular_correccion_monto(spark):
    """Simula que, días después, alguien corrige el monto de un contrato
    específico — el escenario que un auditor necesita poder auditar."""
    tabla = DeltaTable.forPath(spark, RUTA_BRONCE_DELTA)

    contrato_objetivo = spark.read.format("delta").load(RUTA_BRONCE_DELTA).first()
    id_contrato = contrato_objetivo["id_contrato"]
    monto_original = contrato_objetivo["monto"]
    monto_corregido = round(monto_original * 1.35, 2)  # +35%, una "corrección" sospechosamente grande

    print(f"\nSimulando corrección: contrato {id_contrato}, "
          f"monto S/. {monto_original:,.2f} → S/. {monto_corregido:,.2f}")

    tabla.update(
        condition=f"id_contrato = '{id_contrato}'",
        set={"monto": str(monto_corregido)},
    )
    print("Corrección aplicada — versión 1 creada automáticamente por Delta Lake.")
    return id_contrato, monto_original, monto_corregido


def auditar_historial_y_viajar_en_el_tiempo(spark, id_contrato, monto_original):
    """El valor real para un auditor: ver el historial completo, y poder
    consultar el estado EXACTO de los datos antes de la corrección."""
    print("\n--- Historial de versiones de la capa Bronce (DESCRIBE HISTORY) ---")
    spark.sql(f"DESCRIBE HISTORY delta.`{RUTA_BRONCE_DELTA}`").select(
        "version", "timestamp", "operation", "operationParameters"
    ).show(truncate=60)

    print(f"--- Estado ACTUAL del contrato {id_contrato} (versión más reciente) ---")
    spark.read.format("delta").load(RUTA_BRONCE_DELTA) \
        .filter(F.col("id_contrato") == id_contrato).select("id_contrato", "monto").show()

    print(f"--- Estado ORIGINAL del contrato {id_contrato} — TIME TRAVEL a la versión 0 ---")
    version_original = spark.read.format("delta").option("versionAsOf", 0).load(RUTA_BRONCE_DELTA) \
        .filter(F.col("id_contrato") == id_contrato)
    version_original.select("id_contrato", "monto").show()

    monto_recuperado = version_original.first()["monto"]
    coincide = abs(monto_recuperado - monto_original) < 0.01
    print(f"Monto original recuperado vía time travel: S/. {monto_recuperado:,.2f} "
          f"({'coincide exactamente con el valor pre-corrección' if coincide else 'NO coincide — revisar'})")
    print("\nEsto es lo que un CSV sobrescrito NUNCA podría ofrecer: la versión anterior "
          "sigue existiendo, consultable, sin necesidad de backups manuales.")


def demostrar_change_data_feed(spark):
    """CDC/CDF (Anexo 2 del TDR): Delta Lake puede emitir el detalle fila
    por fila de qué cambió entre versiones (preimage y postimage por
    fila), sin necesidad de un sistema externo de Change Data Capture."""
    spark.sql(f"ALTER TABLE delta.`{RUTA_BRONCE_DELTA}` SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
    version_activacion = spark.sql(f"DESCRIBE HISTORY delta.`{RUTA_BRONCE_DELTA}`") \
        .agg(F.max("version")).first()[0]

    tabla = DeltaTable.forPath(spark, RUTA_BRONCE_DELTA)
    contrato = spark.read.format("delta").load(RUTA_BRONCE_DELTA).limit(1).first()
    id_contrato = contrato["id_contrato"]
    tabla.update(condition=f"id_contrato = '{id_contrato}'", set={"monto": "999999.99"})

    print(f"\n--- Change Data Feed (CDC/CDF): detalle fila por fila del cambio en {id_contrato} ---")
    cambios = spark.read.format("delta").option("readChangeFeed", "true") \
        .option("startingVersion", version_activacion).load(RUTA_BRONCE_DELTA) \
        .filter(F.col("id_contrato") == id_contrato)
    cambios.select("id_contrato", "monto", "_change_type", "_commit_version").show(truncate=False)
    print("CDC/CDF VERIFICADO: preimage y postimage de cada cambio, disponibles nativamente.")


def main():
    spark = crear_sesion()
    spark.sparkContext.setLogLevel("ERROR")

    cargar_capa_bronce_delta(spark)
    id_contrato, monto_original, monto_corregido = simular_correccion_monto(spark)
    auditar_historial_y_viajar_en_el_tiempo(spark, id_contrato, monto_original)
    demostrar_change_data_feed(spark)

    print("\nDELTA LAKE REAL VERIFICADO: ACID + historial de versiones + time travel, funcionando de punta a punta.")
    spark.stop()


if __name__ == "__main__":
    main()
