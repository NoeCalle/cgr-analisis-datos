"""Conector Spark SQL para tablas/vistas del Lakehouse institucional."""

import re

from connectors.base import DataConnector

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_\.]+$")


class SparkSqlConnector(DataConnector):
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
        _validate_identifier(table, "tabla")
        sdf = self._session().table(table)
        if columns:
            for column in columns:
                _validate_identifier(column, "columna")
            sdf = sdf.select(*columns)
        return sdf.toPandas()

    def close(self):
        if self._owns_session and self._spark is not None:
            self._spark.stop()
            self._spark = None


def _validate_identifier(value, kind):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"Identificador Spark de {kind} no permitido: {value!r}")
