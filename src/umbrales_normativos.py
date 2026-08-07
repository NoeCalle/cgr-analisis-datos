"""
Umbrales normativos de Adjudicación Simplificada — parametrizados por año
y tipo de contratación (bienes/servicios vs. obras), no un valor único.

Corrección tras revisión técnica externa: la versión anterior de este
prototipo usaba un único umbral fijo (S/. 400,000) para TODOS los objetos
contractuales y TODOS los años. Eso es incorrecto: la Ley de Contrataciones
del Estado fija topes distintos para obras que para bienes/servicios, y
esos montos se actualizan cada año en la Ley de Presupuesto del Sector
Público, en función de la UIT vigente.

Fuentes verificadas:
  - 2022: Ley N.º 31365 (Ley de Presupuesto 2022) + D.S. N.º 398-2021-EF
    (UIT 2022). Bienes/servicios: hasta S/. 400,000. Obras: hasta
    S/. 1,800,000. (Nota: 2022 tuvo dos sub-períodos, "2022-1" y "2022-2",
    con UIT ligeramente distinta; se usa aquí el tope "2022-1", el
    predominante en el año.)
  - 2024: Ley N.º 31953 (Ley de Presupuesto 2024). Bienes/servicios: hasta
    S/. 480,000. Obras: hasta S/. 2,800,000.

LIMITACIÓN DOCUMENTADA: no se verificaron individualmente los topes de
2023, 2025 y 2026 contra la Ley de Presupuesto de cada año — se
aproximan por continuidad con el año verificado más cercano (ver
comentarios en la tabla). Para un despliegue real, estos valores deben
confirmarse contra la Ley de Presupuesto del Sector Público del año
correspondiente y el Reglamento de la Ley de Contrataciones del Estado
vigente (Ley 32069 desde abril 2025).
"""

import pandas as pd

UMBRALES_ADJUDICACION_SIMPLIFICADA = {
    2022: {"bienes_servicios": 400_000, "obras": 1_800_000},   # verificado: Ley 31365
    2023: {"bienes_servicios": 400_000, "obras": 1_800_000},   # aproximado por continuidad con 2022, NO verificado individualmente
    2024: {"bienes_servicios": 480_000, "obras": 2_800_000},   # verificado: Ley 31953
    2025: {"bienes_servicios": 480_000, "obras": 2_800_000},   # aproximado por continuidad con 2024, NO verificado individualmente
    2026: {"bienes_servicios": 480_000, "obras": 2_800_000},   # aproximado por continuidad con 2024, NO verificado individualmente
}

# Palabras clave para clasificar un "objeto" contractual como obra (sujeto
# al tope de obras) en vez de bien/servicio. Simplificación documentada:
# la calificación legal real depende del expediente técnico, no solo del
# texto de la descripción.
PALABRAS_CLAVE_OBRA = ("obra", "construcción", "vial", "rehabilitación", "infraestructura")


def es_categoria_obra(objeto: str) -> bool:
    if pd.isna(objeto):
        return False
    texto = str(objeto).lower()
    return any(palabra in texto for palabra in PALABRAS_CLAVE_OBRA)


def obtener_umbral(fecha, objeto) -> float:
    """Devuelve el umbral de Adjudicación Simplificada aplicable a un
    contrato específico, según su año y si su objeto califica como obra."""
    anio = pd.Timestamp(fecha).year
    tabla = UMBRALES_ADJUDICACION_SIMPLIFICADA.get(anio)
    if tabla is None:
        anio_cercano = min(UMBRALES_ADJUDICACION_SIMPLIFICADA.keys(), key=lambda y: abs(y - anio))
        tabla = UMBRALES_ADJUDICACION_SIMPLIFICADA[anio_cercano]
    categoria = "obras" if es_categoria_obra(objeto) else "bienes_servicios"
    return tabla[categoria]


def umbral_vectorizado(fechas, objetos) -> pd.Series:
    """Versión vectorizada de obtener_umbral() para aplicar sobre una
    Serie/columna completa de un DataFrame de una sola vez."""
    return pd.Series(
        [obtener_umbral(f, o) for f, o in zip(fechas, objetos)],
        index=fechas.index if hasattr(fechas, "index") else None,
    )
