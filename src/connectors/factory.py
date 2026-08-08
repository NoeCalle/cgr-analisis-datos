"""Factoría de conectores a partir de configuración validada."""

from connectors.local_csv import LocalCsvConnector
from connectors.spark_sql import SparkSqlConnector
from connectors.sqlserver import SqlServerConnector


def crear_connector(config, *, spark=None):
    source = config["source"]
    source_type = source["type"]

    if source_type == "local_csv":
        return LocalCsvConnector(source["datasets"])
    if source_type == "sqlserver":
        return SqlServerConnector(source["tables"], source["connection_env"])
    if source_type == "spark_sql":
        return SparkSqlConnector(source["tables"], spark=spark)

    raise ValueError(f"Tipo de fuente no soportado: {source_type!r}")
