"""Conector CSV para preservar el modo PoC/local."""

from pathlib import Path

import pandas as pd

from connectors.base import DataConnector


class LocalCsvConnector(DataConnector):
    def __init__(self, datasets):
        self.datasets = dict(datasets)

    def read(self, domain, columns=None):
        if domain not in self.datasets:
            raise KeyError(f"No hay dataset configurado para {domain!r}.")
        path = Path(self.datasets[domain])
        if not path.exists():
            raise FileNotFoundError(f"Dataset CSV no encontrado para {domain!r}: {path}")
        # La fuente se lee como texto para no destruir identificadores con ceros
        # a la izquierda. El contrato canónico convierte después monto/fecha/bool.
        df = pd.read_csv(path, dtype="string")
        if columns is not None:
            missing = sorted(set(columns) - set(df.columns))
            if missing:
                raise ValueError(f"{path} no contiene columnas requeridas: {missing}")
            df = df.loc[:, list(columns)]
        return df
