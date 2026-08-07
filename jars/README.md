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

## Hadoop Client Minicluster (intento incompleto, documentado con honestidad)
org.apache.hadoop:hadoop-client-minicluster:3.1.1 (27.1 MB) — la utilidad
oficial que el propio equipo de Apache Hadoop usa para sus pruebas
automatizadas (contiene MiniDFSCluster y MiniYARNCluster, HDFS y YARN
reales corriendo en un solo proceso). Se descargó como alternativa liviana
al tarball completo de Hadoop (554 MB) para intentar cerrar la última
brecha del Anexo 2 del TDR.

**No se pudo completar**: este jar solo trae las clases de prueba, no las
clases base (`org.apache.hadoop.conf.Configuration`, etc.), que viven en
`hadoop-client-runtime` — un segundo archivo que normalmente pesa 40-70 MB,
de nuevo por encima del límite de subida de archivos de este entorno
(30 MB). Ver `src/spark/hadoop_mini/TestMiniCluster.java` para el código
que se alcanzó a escribir, y el reporte técnico (Anexo B, Producto 7
Sección 11) para la explicación completa.

Aclaración: esto NO significa que HDFS/YARN sean imposibles de correr en
una sola máquina — Apache documenta explícitamente un modo
pseudo-distribuido (single-node) para exactamente ese caso. Lo que faltó
fue el archivo, no la viabilidad técnica. Lo que sí es una limitación de
fondo, independiente del tamaño de archivo, es que el beneficio real de
HDFS/YARN en producción (replicación tolerante a fallos, reparto de
recursos entre nodos) requiere varias máquinas físicas distintas.
