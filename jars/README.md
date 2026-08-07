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

## Delta Lake (Spark 4.1 / Scala 2.13)
io.delta:delta-spark_4.1_2.13:4.3.0 y io.delta:delta-storage:4.3.0,
mismo origen y mismo motivo que los de GraphFrames (Maven Central,
descargados fuera de este entorno). Nota: la primera versión probada
(delta-spark_2.13:4.0.0, sin sufijo de versión de Spark) falló por
incompatibilidad — Delta Lake 4.1+ publica artefactos específicos por
versión de Spark (`_4.1_` en el nombre) que hay que hacer coincidir
exactamente con la versión de PySpark instalada.
