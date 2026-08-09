"""Conector Spark SQL para tablas/vistas del Lakehouse institucional.

A diferencia de los conectores CSV/SQL Server, ``read`` devuelve un DataFrame
Spark. La capa de integración Spark-native decide cómo mapear y validar sin
materializar el dataset completo en memoria del driver.
"""

from connectors.base import DataConnector


class SparkSqlConnector(DataConnector):
    native_engine = "spark"

    def __init__(self, tables, spark=None):
        self.tables = dict(tables)
        self._spark = spark
        self._owns_session = spark is None

    def _session(self):
        if self._spark is not None:
            return self._spark
        from pyspark.sql import SparkSession

        # No se fuerza master aquí. En entorno CGR Spark toma la configuración
        # de spark-submit/Airflow/YARN/Kubernetes; local puede definirla fuera.
        self._spark = SparkSession.builder.appName("cgr-integracion-datos").getOrCreate()
        return self._spark

    def read(self, domain, columns=None):
        if domain not in self.tables:
            raise KeyError(f"No hay tabla Spark SQL configurada para {domain!r}.")
        table = self.tables[domain]
        if not isinstance(table, str) or not table.strip():
            raise ValueError(f"Tabla Spark inválida para {domain!r}: {table!r}")

        # `table()` y `select()` usan la API DataFrame, no interpolación SQL.
        sdf = self._session().table(table)
        if columns:
            if any(not isinstance(c, str) or not c.strip() for c in columns):
                raise ValueError("Las columnas Spark configuradas deben ser nombres no vacíos.")
            sdf = sdf.select(*columns)
        return sdf

    def close(self):
        if self._owns_session and self._spark is not None:
            self._spark.stop()
            self._spark = None
