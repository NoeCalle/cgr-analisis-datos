"""
Motor normativo de umbrales para señales de posible fraccionamiento.

No determina por sí solo la existencia jurídica de fraccionamiento. Su función
es parametrizar una SEÑAL DE ALERTA para priorización de revisión por auditor,
usando la cuantía que separa el procedimiento general del procedimiento
simplificado/abreviado según año, régimen y tipo de contratación.

Fuentes verificadas (OSCE/OECE/MEF):
  - 2018: bienes/servicios S/ 400,000; obras S/ 1,800,000.
  - 2019: bienes/servicios S/ 400,000; obras S/ 1,800,000.
  - 2020: bienes/servicios S/ 400,000; obras S/ 1,800,000.
  - 2021: bienes/servicios S/ 400,000; obras S/ 1,800,000.
  - 2022: bienes/servicios S/ 400,000; obras S/ 2,800,000.
  - 2023: bienes/servicios S/ 480,000; obras S/ 2,800,000.
  - 2024: bienes/servicios S/ 480,000; obras S/ 2,800,000.
  - 2025: bienes/servicios S/ 485,000; obras S/ 5,000,000.
  - Desde 22/04/2025 entra en vigencia la Ley 32069. Los montos 2025 se
    mantienen, pero cambian los procedimientos (p. ej. licitación/concurso
    público abreviado en lugar de adjudicación simplificada).
  - 2026: bienes/servicios S/ 485,000; obras S/ 5,000,000, bajo Ley 32069.

La inclusión 2018-2021 es necesaria porque la publicación OCDS usada como
prueba real, aunque segmentada principalmente en 2022, contiene contratos
firmados desde 2018. No se aproxima silenciosamente un año desconocido.

Sprint 4 incorpora procedencia versionada para 2023-2026, que es el rango del
dataset sintético principal. La clasificación de modalidades es REFERENCIAL:
una cuantía no permite por sí sola decidir la procedencia jurídica de
Contratación Directa, Comparación de Precios, Subasta Inversa, acuerdos marco u
otros supuestos especiales.

En producción institucional esta tabla debe versionarse como dato maestro
normativo y validarse cuando se publique cada Ley de Presupuesto anual.
"""

from __future__ import annotations

import unicodedata

import pandas as pd

FECHA_VIGENCIA_LEY_32069 = pd.Timestamp("2025-04-22")

UMBRALES_PROCEDIMIENTO_SIMPLIFICADO_ABREVIADO = {
    2018: {"bienes_servicios": 400_000.0, "obras": 1_800_000.0},
    2019: {"bienes_servicios": 400_000.0, "obras": 1_800_000.0},
    2020: {"bienes_servicios": 400_000.0, "obras": 1_800_000.0},
    2021: {"bienes_servicios": 400_000.0, "obras": 1_800_000.0},
    2022: {"bienes_servicios": 400_000.0, "obras": 2_800_000.0},
    2023: {"bienes_servicios": 480_000.0, "obras": 2_800_000.0},
    2024: {"bienes_servicios": 480_000.0, "obras": 2_800_000.0},
    2025: {"bienes_servicios": 485_000.0, "obras": 5_000_000.0},
    2026: {"bienes_servicios": 485_000.0, "obras": 5_000_000.0},
}

# Alias conservado por compatibilidad con scripts/documentación previa.
UMBRALES_ADJUDICACION_SIMPLIFICADA = UMBRALES_PROCEDIMIENTO_SIMPLIFICADO_ABREVIADO

FUENTES_NORMATIVAS = {
    2023: {
        "ley_presupuesto": "Ley N.° 31638 - Presupuesto del Sector Público para el Año Fiscal 2023",
        "url_presupuesto": "https://www.gob.pe/institucion/mef/normas-legales/3715319-31638",
    },
    2024: {
        "ley_presupuesto": "Ley N.° 31953 - Presupuesto del Sector Público para el Año Fiscal 2024",
        "url_presupuesto": "https://www.gob.pe/institucion/mef/normas-legales/6964231-31953",
    },
    2025: {
        "ley_presupuesto": "Ley N.° 32185 - Presupuesto del Sector Público para el Año Fiscal 2025",
        "url_presupuesto": "https://www.gob.pe/institucion/mef/normas-legales/6278077-32185",
        "url_topes": "https://www.gob.pe/77926-montos-para-la-determinacion-de-los-procedimientos-de-seleccion-segun-ley-de-presupuesto-del-sector-publico-para-el-ano-fiscal-2025-ley-32185",
        "ley_regimen": "Ley N.° 32069 - Ley General de Contrataciones Públicas",
        "url_vigencia_regimen": "https://www.gob.pe/institucion/oece/noticias/1153925-oece-inicia-funciones-con-la-entrada-en-vigencia-de-la-nueva-ley-general-de-contrataciones-publicas",
    },
    2026: {
        "ley_presupuesto": "Ley N.° 32513 - Presupuesto del Sector Público para el Año Fiscal 2026",
        "url_presupuesto": "https://www.gob.pe/institucion/mef/normas-legales/7475743-32513",
        "ley_regimen": "Ley N.° 32069 - Ley General de Contrataciones Públicas",
        "url_regimen": "https://www.gob.pe/institucion/oece/colecciones/45029-ley-n-32069-ley-general-de-contrataciones-publicas",
    },
}

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

MODALIDADES_ESPECIALES_NO_INFERIBLES_POR_CUANTIA = (
    "contratacion directa",
    "comparacion de precios",
    "subasta inversa",
    "catalogo electronico",
    "acuerdo marco",
    "compra corporativa",
    "dialogo competitivo",
    "compra publica de innovacion",
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


def _tipo_estructurado(categoria_principal) -> str | None:
    if categoria_principal is None or pd.isna(categoria_principal):
        return None
    valor = str(categoria_principal).strip().lower()
    if valor in {"works", "obra", "obras"}:
        return "works"
    if valor in {"goods", "bien", "bienes"}:
        return "goods"
    if valor in {"services", "servicio", "servicios", "consultingservices", "consulting services"}:
        return "services"
    return None


def obtener_nombre_procedimiento(fecha, objeto=None, categoria_principal=None) -> str:
    """Nombre referencial del procedimiento por debajo de la cuantía superior."""
    categoria = obtener_categoria_umbral(objeto, categoria_principal)
    if obtener_regimen(fecha) == "Ley 30225":
        return "Adjudicación Simplificada"
    if categoria == "obras":
        return "Licitación Pública Abreviada"
    tipo = _tipo_estructurado(categoria_principal)
    if tipo == "services":
        return "Concurso Público Abreviado"
    if tipo == "goods":
        return "Licitación Pública Abreviada"
    return "Licitación/Concurso Público Abreviado"


def obtener_umbral(fecha, objeto=None, categoria_principal=None) -> float:
    """Devuelve la cuantía superior aplicable a la señal de alerta.

    No se aproxima silenciosamente un año desconocido con el año más cercano.
    """
    anio = pd.Timestamp(fecha).year
    if anio not in UMBRALES_PROCEDIMIENTO_SIMPLIFICADO_ABREVIADO:
        raise ValueError(
            f"No existe umbral normativo parametrizado para {anio}. "
            "Actualizar UMBRALES_PROCEDIMIENTO_SIMPLIFICADO_ABREVIADO con fuente oficial."
        )
    categoria = obtener_categoria_umbral(objeto, categoria_principal)
    return UMBRALES_PROCEDIMIENTO_SIMPLIFICADO_ABREVIADO[anio][categoria]


def obtener_procedimiento_referencial_por_cuantia(
    fecha, monto, objeto=None, categoria_principal=None
) -> str | None:
    """Procedimiento general/abreviado esperable SOLO como referencia por cuantía.

    No sustituye el análisis del supuesto jurídico de contratación. Para
    modalidades especiales la clasificación posterior las marca como no
    inferibles exclusivamente por monto.
    """
    if monto is None or pd.isna(monto):
        return None
    umbral = obtener_umbral(fecha, objeto=objeto, categoria_principal=categoria_principal)
    if float(monto) < umbral:
        return obtener_nombre_procedimiento(
            fecha, objeto=objeto, categoria_principal=categoria_principal
        )

    tipo = _tipo_estructurado(categoria_principal)
    if tipo == "services":
        return "Concurso Público"
    if tipo in {"goods", "works"}:
        return "Licitación Pública"
    if es_categoria_obra(objeto, categoria_principal):
        return "Licitación Pública"
    return "Licitación/Concurso Público"


def _normalizar_texto(valor) -> str:
    if valor is None or pd.isna(valor):
        return ""
    texto = unicodedata.normalize("NFKD", str(valor).strip().lower())
    return "".join(ch for ch in texto if not unicodedata.combining(ch))


def clasificar_modalidad_frente_regimen(
    fecha, monto, modalidad, objeto=None, categoria_principal=None
) -> dict:
    """Compara modalidad observada con una referencia por cuantía, sin juicio legal."""
    if modalidad is None or pd.isna(modalidad) or not str(modalidad).strip():
        return {
            "clasificacion": "sin_informacion",
            "procedimiento_referencial": obtener_procedimiento_referencial_por_cuantia(
                fecha, monto, objeto=objeto, categoria_principal=categoria_principal
            ),
        }

    modalidad_norm = _normalizar_texto(modalidad)
    procedimiento = obtener_procedimiento_referencial_por_cuantia(
        fecha, monto, objeto=objeto, categoria_principal=categoria_principal
    )

    if any(token in modalidad_norm for token in MODALIDADES_ESPECIALES_NO_INFERIBLES_POR_CUANTIA):
        clasificacion = "especial_no_inferible_por_cuantia"
    elif procedimiento is None:
        clasificacion = "sin_cuantia_para_comparar"
    else:
        proc_norm = _normalizar_texto(procedimiento)
        compatibles = {proc_norm}
        if "/" in procedimiento:
            if "abreviado" in proc_norm:
                compatibles |= {
                    _normalizar_texto("Licitación Pública Abreviada"),
                    _normalizar_texto("Concurso Público Abreviado"),
                }
            else:
                compatibles |= {
                    _normalizar_texto("Licitación Pública"),
                    _normalizar_texto("Concurso Público"),
                }
        clasificacion = (
            "compatible_referencial_por_cuantia"
            if modalidad_norm in compatibles
            else "requiere_revision_contexto"
        )

    return {
        "clasificacion": clasificacion,
        "procedimiento_referencial": procedimiento,
    }


def obtener_fuentes_normativas(fecha) -> dict:
    """Devuelve procedencia versionada cuando el año está documentado en el PoC."""
    anio = pd.Timestamp(fecha).year
    return dict(FUENTES_NORMATIVAS.get(anio, {}))


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
        "fuentes_normativas": obtener_fuentes_normativas(fecha_ts),
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
