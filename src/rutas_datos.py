"""Resolución de rutas de datos para el PoC local.

El pipeline orquestado debe consumir Plata y publicar Oro. Para permitir que
scripts individuales sigan siendo ejecutables durante desarrollo, se admite un
fallback explícito a data/ cuando el artefacto Plata aún no fue publicado.
Ese fallback se anuncia por consola y no debe confundirse con el flujo del DAG.
"""

from pathlib import Path

PLATA = Path("lakehouse/plata")
ORO = Path("lakehouse/oro")
DATA = Path("data")
OUTPUTS = Path("outputs")


def entrada_plata(nombre: str, fallback_data: bool = True) -> Path:
    ruta = PLATA / nombre
    if ruta.exists():
        return ruta
    if fallback_data:
        fallback = DATA / nombre
        if fallback.exists():
            print(f"ADVERTENCIA: {ruta} no existe; ejecución standalone usa fallback {fallback}.")
            return fallback
    raise FileNotFoundError(
        f"No existe {ruta}. Ejecutar preprocesamiento y `python3 src/lakehouse_capas.py plata`."
    )


def entrada_oro(nombre: str, fallback_outputs: bool = True) -> Path:
    ruta = ORO / nombre
    if ruta.exists():
        return ruta
    if fallback_outputs:
        fallback = OUTPUTS / nombre
        if fallback.exists():
            print(f"ADVERTENCIA: {ruta} no existe; ejecución standalone usa fallback {fallback}.")
            return fallback
    raise FileNotFoundError(
        f"No existe {ruta}. Ejecutar modelos y `python3 src/lakehouse_capas.py oro`."
    )
