"""
Capas locales Bronce/Plata/Oro — simulación arquitectónica del Anexo 2.

No pretende ser el Lakehouse institucional. La mejora P1 hace que las capas
sean funcionales dentro del PoC:
- Bronce: fuentes sintéticas sin transformar.
- Plata: contratos limpiados, features y dimensiones necesarias.
- Modelos: consumen preferentemente datasets de Plata.
- Oro: rankings/señales listos para integración y reporting.
"""

import shutil
from pathlib import Path

BRONCE = Path("lakehouse/bronce")
PLATA = Path("lakehouse/plata")
ORO = Path("lakehouse/oro")


def preparar_carpetas():
    for capa in (BRONCE, PLATA, ORO):
        capa.mkdir(parents=True, exist_ok=True)


def _copiar_si_existe(origen: Path, destino: Path) -> bool:
    if not origen.exists():
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, destino)
    return True


def cargar_a_bronce():
    """Ingesta cruda: copia sin transformación."""
    preparar_carpetas()
    nombres = [
        "contratos_siaf_seace.csv", "proveedores.csv", "entidades.csv", "funcionarios.csv"
    ]
    copiados = sum(
        _copiar_si_existe(Path("data") / nombre, BRONCE / nombre)
        for nombre in nombres
    )
    print(f"Capa Bronce: {copiados}/{len(nombres)} fuentes publicadas sin transformar.")


def mover_a_plata():
    """Publica los datos limpios/features que deben consumir los modelos."""
    preparar_carpetas()
    archivos = [
        ("data/contratos_procesados.csv", "contratos_procesados.csv"),
        ("data/dataset_favoritismo.csv", "dataset_favoritismo.csv"),
        ("data/dataset_fraccionamiento.csv", "dataset_fraccionamiento.csv"),
        # Dimensiones del PoC; en CGR serían tablas Plata institucionales.
        ("data/proveedores.csv", "proveedores.csv"),
        ("data/entidades.csv", "entidades.csv"),
        ("data/funcionarios.csv", "funcionarios.csv"),
    ]
    faltantes = []
    for origen, destino in archivos:
        if not _copiar_si_existe(Path(origen), PLATA / destino):
            faltantes.append(origen)
    if faltantes:
        raise FileNotFoundError(
            "No se puede publicar Plata; faltan artefactos esperados: " + ", ".join(faltantes)
        )
    print(f"Capa Plata: {len(archivos)} datasets limpios/features/dimensiones publicados.")


def mover_a_oro():
    """Publica únicamente salidas de negocio/modelo para consumo downstream."""
    preparar_carpetas()
    archivos = [
        ("outputs/ranking_riesgo_favoritismo.csv", "ranking_riesgo_favoritismo.csv"),
        ("outputs/ranking_riesgo_fraccionamiento.csv", "ranking_riesgo_fraccionamiento.csv"),
        ("outputs/ranking_vinculos_proveedor_funcionario.csv", "ranking_vinculos_proveedor_funcionario.csv"),
    ]
    faltantes = []
    for origen, destino in archivos:
        if not _copiar_si_existe(Path(origen), ORO / destino):
            faltantes.append(origen)
    if faltantes:
        raise FileNotFoundError(
            "No se puede publicar Oro; faltan salidas esperadas: " + ", ".join(faltantes)
        )
    print(f"Capa Oro: {len(archivos)} salidas de negocio publicadas.")


if __name__ == "__main__":
    import sys

    accion = sys.argv[1] if len(sys.argv) > 1 else "todo"
    if accion in ("bronce", "todo"):
        cargar_a_bronce()
    if accion in ("plata", "todo"):
        mover_a_plata()
    if accion in ("oro", "todo"):
        mover_a_oro()
