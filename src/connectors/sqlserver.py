"""Conector SQL Server con credenciales suministradas por variable de entorno.

`pyodbc` se importa de forma diferida para que el PoC local no requiera un
driver SQL Server. El entorno institucional debe instalar el driver ODBC que
corresponda a su plataforma y proporcionar la cadena en `connection_env`.
"""

import os
import re

import pandas as pd

from connectors.base import DataConnector

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_\.\[\]]+$")


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
        table = self.tables[domain]
        _validate_identifier(table, "tabla")
        if columns:
            for column in columns:
                _validate_identifier(column, "columna")
            projection = ", ".join(columns)
        else:
            projection = "*"
        query = f"SELECT {projection} FROM {table}"
        return pd.read_sql_query(query, self._connect())

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def _validate_identifier(value, kind):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"Identificador de {kind} no permitido: {value!r}")
