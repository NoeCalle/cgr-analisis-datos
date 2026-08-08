"""Conector SQL Server con credenciales suministradas por variable de entorno.

`pyodbc` se importa de forma diferida para que el PoC local no requiera un
driver SQL Server. El entorno institucional debe instalar el driver ODBC que
corresponda a su plataforma y proporcionar la cadena en `connection_env`.
"""

import os

import pandas as pd

from connectors.base import DataConnector


class SqlServerConnector(DataConnector):
    def __init__(self, tables, connection_env):
        self.tables = dict(tables)
        self.connection_env = connection_env
        self._conn = None

    def _connect(self):
        if self._conn is not None:
            return self._conn
        connection_string = os.environ.get(self.connection_env)
        if not connection_string:
            raise RuntimeError(
                f"Falta la variable de entorno {self.connection_env!r} con la conexión SQL Server."
            )
        try:
            import pyodbc
        except ImportError as exc:
            raise RuntimeError(
                "El conector SQL Server requiere pyodbc y un driver ODBC institucional. "
                "Instale las dependencias del entorno CGR antes de usar source.type=sqlserver."
            ) from exc
        self._conn = pyodbc.connect(connection_string)
        return self._conn

    def read(self, domain, columns=None):
        if domain not in self.tables:
            raise KeyError(f"No hay tabla SQL Server configurada para {domain!r}.")
        table = _quote_qualified_identifier(self.tables[domain])
        projection = "*" if not columns else ", ".join(_quote_identifier(c) for c in columns)
        query = f"SELECT {projection} FROM {table}"
        return pd.read_sql_query(query, self._connect())

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def _quote_identifier(value):
    """Escapa un identificador T-SQL sin permitir que se convierta en SQL libre."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Identificador SQL Server inválido: {value!r}")
    if "\x00" in value or ";" in value or "--" in value or "/*" in value or "*/" in value:
        raise ValueError(f"Identificador SQL Server no permitido: {value!r}")
    raw = value.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    return "[" + raw.replace("]", "]]" ) + "]"


def _quote_qualified_identifier(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Tabla SQL Server inválida: {value!r}")
    parts = [part.strip() for part in value.split(".")]
    if any(not part for part in parts):
        raise ValueError(f"Tabla SQL Server inválida: {value!r}")
    return ".".join(_quote_identifier(part) for part in parts)
