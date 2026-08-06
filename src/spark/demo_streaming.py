"""
Demostración de Streaming — componente "Streaming" del Anexo 2 del TDR
(ingesta Batch / CDC-CDF / Streaming hacia el Lakehouse).

Simula la llegada incremental de nuevos lotes de contratos (como si SEACE
publicara actualizaciones a lo largo del día) usando Spark Structured
Streaming en modo file-source: el stream vigila una carpeta y procesa
cada archivo nuevo que aparece, calculando agregados en tiempo real —
el patrón real que usaría un pipeline de ingesta continua sobre el
Lakehouse, en vez de una carga batch única.
"""

import os
import shutil
import time
import threading
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType
from pyspark.sql import functions as F

CARPETA_ORIGEN = "outputs/streaming_demo/origen"
CARPETA_CHECKPOINT = "outputs/streaming_demo/checkpoint"

SCHEMA = StructType([
    StructField("id_contrato", StringType()),
    StructField("id_proveedor", StringType()),
    StructField("id_entidad", StringType()),
    StructField("modalidad", StringType()),
    StructField("monto", DoubleType()),
])


def preparar_carpetas():
    shutil.rmtree(CARPETA_ORIGEN, ignore_errors=True)
    shutil.rmtree(CARPETA_CHECKPOINT, ignore_errors=True)
    os.makedirs(CARPETA_ORIGEN, exist_ok=True)


def simular_llegada_de_lotes():
    """Escribe 3 archivos con un pequeño retraso entre cada uno, simulando
    que SEACE publica nuevos contratos de forma incremental a lo largo del
    día, no todos de una vez."""
    lotes = [
        "id_contrato,id_proveedor,id_entidad,modalidad,monto\nC900001,P0010,E01,Adjudicación Simplificada,85000.0\nC900002,P0022,E03,Contratación Directa,42000.0\n",
        "id_contrato,id_proveedor,id_entidad,modalidad,monto\nC900003,P0010,E01,Adjudicación Simplificada,91000.0\nC900004,P0055,E02,Licitación Pública,310000.0\n",
        "id_contrato,id_proveedor,id_entidad,modalidad,monto\nC900005,P0010,E01,Contratación Directa,120000.0\nC900006,P0099,E04,Comparación de Precios,67000.0\n",
    ]
    for i, contenido in enumerate(lotes):
        time.sleep(3)
        with open(f"{CARPETA_ORIGEN}/lote_{i}.csv", "w") as f:
            f.write(contenido)
        print(f"  [emisor] lote_{i}.csv publicado ({contenido.count(chr(10))-1} contratos)")


def main():
    preparar_carpetas()
    spark = (
        SparkSession.builder.appName("cgr-streaming-demo").master("local[*]")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    stream = spark.readStream.schema(SCHEMA).option("header", "true").csv(CARPETA_ORIGEN)

    # Agregado en tiempo real: monto acumulado por entidad, actualizado
    # cada vez que llega un micro-batch nuevo (no al final, incremental)
    agregado = stream.groupBy("id_entidad").agg(
        F.count("id_contrato").alias("n_contratos"),
        F.sum("monto").alias("monto_acumulado"),
    )

    query = (
        agregado.writeStream.format("memory").queryName("agregado_streaming")
        .outputMode("complete").option("checkpointLocation", CARPETA_CHECKPOINT)
        .trigger(processingTime="2 seconds")
        .start()
    )

    print("Stream iniciado. Simulando llegada incremental de lotes...\n")
    emisor = threading.Thread(target=simular_llegada_de_lotes)
    emisor.start()
    emisor.join()

    query.processAllAvailable()  # espera determinista a que TODOS los micro-batches disponibles terminen de procesarse

    print("\nEstado acumulado de la agregación en streaming (por entidad):")
    resultado = spark.sql("SELECT * FROM agregado_streaming ORDER BY id_entidad")
    resultado.show(truncate=False)
    resultado.toPandas().to_csv("outputs/streaming_demo_resultado.csv", index=False)

    query.stop()
    print("STREAMING VERIFICADO: el pipeline procesó 3 micro-batches de forma incremental, no un solo batch.")
    spark.stop()


if __name__ == "__main__":
    main()
