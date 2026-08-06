"""
Simulación de capas del Lakehouse — Anexo 2 del TDR ("Arquitectura de la
Plataforma de Minería de Datos"): Bronce (ingesta cruda e histórica),
Plata (filtrado, limpiado y refinado), Oro (nivel de negocio, agregación).

En producción esto NO son carpetas locales sino tablas Delta Lake sobre
Hadoop, gestionadas por HMS/MySQL (ver Anexo 2). Aquí se simula la
organización física en tres carpetas para poder orquestar el pipeline con
Airflow de forma honesta: cada tarea del DAG lee de una capa y escribe en
la siguiente, igual que lo haría un DAG real, sin pretender que esto ES
el Lakehouse de la CGR.
"""

import shutil
from pathlib import Path

BRONCE = Path("lakehouse/bronce")
PLATA = Path("lakehouse/plata")
ORO = Path("lakehouse/oro")


def preparar_carpetas():
    for capa in (BRONCE, PLATA, ORO):
        capa.mkdir(parents=True, exist_ok=True)


def cargar_a_bronce():
    """Ingesta cruda e histórica — copia tal cual, sin transformar."""
    preparar_carpetas()
    for f in ["contratos_siaf_seace.csv", "proveedores.csv", "entidades.csv", "funcionarios.csv"]:
        origen = Path("data") / f
        if origen.exists():
            shutil.copy(origen, BRONCE / f)
    print(f"Capa Bronce: {len(list(BRONCE.glob('*.csv')))} archivos cargados (ingesta cruda).")


def mover_a_plata():
    """Filtrado, limpiado y refinado — el dataset ya procesado por
    src/preprocesamiento.py (imputación, outliers, encoding)."""
    preparar_carpetas()
    origen = Path("data/contratos_procesados.csv")
    if not origen.exists():
        raise FileNotFoundError(
            "data/contratos_procesados.csv no existe — ejecutar src/preprocesamiento.py antes de esta tarea."
        )
    shutil.copy(origen, PLATA / "contratos_procesados.csv")
    print("Capa Plata: contratos_procesados.csv (limpio, sin nulos, sin outliers extremos) publicado.")


def mover_a_oro():
    """Nivel de negocio, agregación — los datasets de features por caso de
    uso y los rankings de riesgo, listos para consumo (equivalente a SSRS/
    Power BI en producción)."""
    preparar_carpetas()
    archivos = [
        ("data/dataset_favoritismo.csv", "dataset_favoritismo.csv"),
        ("data/dataset_fraccionamiento.csv", "dataset_fraccionamiento.csv"),
        ("outputs/ranking_riesgo_favoritismo.csv", "ranking_riesgo_favoritismo.csv"),
        ("outputs/ranking_riesgo_fraccionamiento.csv", "ranking_riesgo_fraccionamiento.csv"),
        ("outputs/ranking_vinculos_proveedor_funcionario.csv", "ranking_vinculos_proveedor_funcionario.csv"),
    ]
    copiados = 0
    for origen, destino in archivos:
        p = Path(origen)
        if p.exists():
            shutil.copy(p, ORO / destino)
            copiados += 1
    print(f"Capa Oro: {copiados}/{len(archivos)} datasets de negocio publicados (listos para SSRS/Power BI).")


if __name__ == "__main__":
    import sys
    accion = sys.argv[1] if len(sys.argv) > 1 else "todo"
    if accion in ("bronce", "todo"):
        cargar_a_bronce()
    if accion in ("plata", "todo"):
        mover_a_plata()
    if accion in ("oro", "todo"):
        mover_a_oro()
