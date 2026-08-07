# JARs de GraphFrames (Spark 4 / Scala 2.13)

io.graphframes:graphframes-spark4_2.13:0.10.0 y su dependencia interna
graphframes-graphx-spark4_2.13:0.10.0, descargados directamente de Maven
Central (repo1.maven.org) fuera de este entorno de desarrollo, porque el
entorno de prueba de concepto no tiene salida de red hacia Maven.

Se versionan aquí (752 KB en total) para que el repositorio sea 100%
reproducible sin depender de que quien lo clone también resuelva el mismo
problema de red.

Uso: `spark.jars` apuntando a ambos archivos (ver
src/spark/vinculos_graphframes.py).
