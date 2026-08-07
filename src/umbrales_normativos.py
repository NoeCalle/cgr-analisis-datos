"""
Motor normativo de umbrales para señales de posible fraccionamiento.

No determina por sí solo la existencia jurídica de fraccionamiento. Su función
es parametrizar una SEÑAL DE ALERTA para priorización de revisión por auditor,
usando la cuantía que separa el procedimiento general del procedimiento
simplificado/abreviado según año, régimen y tipo de contratación.

Fuentes oficiales verificadas (OECE/OSCE/MEF):
  - 2022: bienes/servicios S/ 400,000; obras S/ 2,800,000.
  - 2023: bienes/servicios S/ 480,000; obras S/ 2,800,000.
  - 2024: bienes/servicios S/ 480,000; obras S/ 2,800,000.
  - 2025: bienes/servicios S/ 485,000; obras S/ 5,000,000.
  - Desde 22/04/2025 entra en vigencia la Ley 32069. Los montos 2025 se
    mantienen, pero cambian los procedimientos (p. ej. licitación/concurso
    público abreviado en lugar de adjudicación simplificada).
  - 2026: bienes/servicios S/ 485,000; obras S/ 5,000,000, bajo Ley 32069.

En producción institucional esta tabla debe versionarse como dato maestro
normativo y validarse cuando se publique cada Ley de Presupuesto anual.
"""

from __future__ import annotations

import pandas as pd

FECHA_VIGENCIA_LEY_32069 = pd.Timestamp("2025-04-22")

# Cuantía superior del procedimiento simplificado/abreviado para el régimen
# general. Es una señal para análisis, NO una definición jurídica completa de
# fraccionamiento.
UMBRALES_PROCEDIMIENTO_SIMPLIFICADO_ABREVIADO = {
    2022: {"bienes_servicios": 400_000.0, "obras": 2_800_000.0},
    2023: {"bienes_servicios": 480_000.0, "obras": 2_800_000.0},
    2024: {"bienes_servicios": 480_000.0, "obras": 2_800_000.0},
    2025: {"bienes_servicios": 485_000.0, "obras": 5_000_000.0},
    2026: {"bienes_servicios": 485_000.0, "obras": 5_000_000.0},
}

# Alias conservado por compatibilidad con scripts/documentación previa.
UMBRALES_ADJUDICACION_SIMPLIFICADA = UMBRALES_PROCEDIMIENTO_SIMPLIFICADO_ABREVIADO

# Fallback SOLO para datasets sintéticos o fuentes sin clasificación
# estructurada. En datos OCDS reales debe priorizarse mainProcurementCategory.
PALABRAS_CLAVE_OBRA = (
    "obra",
    "construcción",
    "construccion",
    "vial",
    "carretera",
    "pavimentación",
    "pavimentacion",
    "rehabilitación vial",
    "rehabilitacion vial",
)


def normalizar_categoria_principal(categoria_principal) -> str | None:
    """Normaliza OCDS mainProcurementCategory a la clasificación del motor."""
    if categoria_principal is None or pd.isna(categoria_principal):
        return None
    valor = str(categoria_principal).strip().lower()
    if valor in {"works", "obra", "obras"}:
        return "obras"
    if valor in {
        "goods", "services", "consultingservices", "consulting services",
        "bienes", "servicios", "consultoria", "consultoría",
    }:
        return "bienes_servicios"
    return None


def es_categoria_obra(objeto: str | None, categoria_principal=None) -> bool:
    """Determina si aplica la cuantía de obras.

    Prioridad:
      1) categoría estructurada OCDS (`mainProcurementCategory`), si existe;
      2) fallback conservador por texto para datos sintéticos/no estructurados.

    El fallback evita usar la palabra genérica "infraestructura" porque una
    descripción como "Servicio de mantenimiento de infraestructura" no es, por
    sí sola, evidencia suficiente para clasificar el contrato como obra.
    """
    categoria = normalizar_categoria_principal(categoria_principal)
    if categoria is not None:
        return categoria == "obras"
    if objeto is None or pd.isna(objeto):
        return False
    texto = str(objeto).lower()
    return any(palabra in texto for palabra in PALABRAS_CLAVE_OBRA)


def obtener_regimen(fecha) -> str:
    fecha = pd.Timestamp(fecha)
    return "Ley 32069" if fecha >= FECHA_VIGENCIA_LEY_32069 else "Ley 30225"


def obtener_categoria_umbral(objeto=None, categoria_principal=None) -> str:
    return "obras" if es_categoria_obra(objeto, categoria_principal) else "bienes_servicios"


def obtener_nombre_procedimiento(fecha, objeto=None, categoria_principal=None) -> str:
    """Nombre referencial del procedimiento por debajo de la cuantía superior."""
    categoria = obtener_categoria_umbral(objeto, categoria_principal)
    if obtener_regimen(fecha) == "Ley 30225":
        return "Adjudicación Simplificada"
    if categoria == "obras":
        return "Licitación Pública Abreviada"
    valor = "" if categoria_principal is None or pd.isna(categoria_principal) else str(categoria_principal).strip().lower()
    if valor == "services":
        return "Concurso Público Abreviado"
    if valor == "goods":
        return "Licitación Pública Abreviada"
    return "Licitación/Concurso Público Abreviado"


def obtener_umbral(fecha, objeto=None, categoria_principal=None) -> float:
    """Devuelve la cuantía superior aplicable a la señal de alerta.

    No se aproxima silenciosamente un año desconocido con el año más cercano.
    Si falta parametrización se falla explícitamente para impedir que una regla
    desactualizada genere alertas con apariencia de validez normativa.
    """
    anio = pd.Timestamp(fecha).year
    if anio not in UMBRALES_PROCEDIMIENTO_SIMPLIFICADO_ABREVIADO:
        raise ValueError(
            f"No existe umbral normativo parametrizado para {anio}. "
            "Actualizar UMBRALES_PROCEDIMIENTO_SIMPLIFICADO_ABREVIADO con fuente oficial."
        )
    categoria = obtener_categoria_umbral(objeto, categoria_principal)
    return UMBRALES_PROCEDIMIENTO_SIMPLIFICADO_ABREVIADO[anio][categoria]


def obtener_contexto_normativo(fecha, objeto=None, categoria_principal=None) -> dict:
    """Devuelve metadatos auditables junto con la cuantía aplicada."""
    fecha_ts = pd.Timestamp(fecha)
    categoria = obtener_categoria_umbral(objeto, categoria_principal)
    return {
        "anio": fecha_ts.year,
        "regimen": obtener_regimen(fecha_ts),
        "categoria_umbral": categoria,
        "procedimiento_referencial": obtener_nombre_procedimiento(
            fecha_ts, objeto=objeto, categoria_principal=categoria_principal
        ),
        "umbral": obtener_umbral(fecha_ts, objeto=objeto, categoria_principal=categoria_principal),
    }


def umbral_vectorizado(fechas, objetos=None, categorias_principales=None) -> pd.Series:
    """Versión vectorizada compatible con pandas."""
    if objetos is None:
        objetos = [None] * len(fechas)
    if categorias_principales is None:
        categorias_principales = [None] * len(fechas)
    return pd.Series(
        [
            obtener_umbral(f, objeto=o, categoria_principal=c)
            for f, o, c in zip(fechas, objetos, categorias_principales)
        ],
        index=fechas.index if hasattr(fechas, "index") else None,
    )
