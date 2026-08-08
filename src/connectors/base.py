"""Interfaz comun para fuentes de datos."""

class DataConnector:
    def read(self, domain, columns=None):
        raise NotImplementedError

    def close(self):
        return None
