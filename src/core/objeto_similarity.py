"""Normalización reproducible para agrupar objetos contractuales similares.

No pretende resolver similitud semántica general ni sustituir una taxonomía
institucional. Proporciona una señal lexical conservadora para que pequeñas
variantes de redacción no fragmenten automáticamente una serie temporal.

La salida se usa como clave analítica de fraccionamiento y siempre debe
conservarse junto al texto original para revisión humana.
"""

from __future__ import annotations

import re
import unicodedata


STOPWORDS = {
    "de", "del", "la", "las", "el", "los", "y", "e", "para", "por", "con",
    "en", "a", "un", "una", "unos", "unas", "servicio", "servicios",
    "adquisicion", "adquisiciones", "contratacion", "contrataciones",
    "compra", "compras", "obra", "obras", "publica", "publico",
    "preventivo", "preventiva", "preventivos", "preventivas",
    "correctivo", "correctiva", "correctivos", "correctivas",
}

# Equivalencias deliberadamente pequeñas. Solo colapsan vocablos cercanos en
# el contexto de descripción contractual; no infieren identidad jurídica del
# objeto ni reemplazan catálogos/clasificadores aprobados por CGR.
SYNONYMS = {
    "conservacion": "mantenimiento",
    "conservar": "mantenimiento",
    "mantenimientos": "mantenimiento",
    "vias": "via",
    "vial": "via",
    "viales": "via",
    "carretera": "via",
    "carreteras": "via",
    "equipos": "equipo",
    "informaticos": "informatico",
    "informaticas": "informatico",
    "materiales": "material",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)


def normalizar_texto_objeto(valor) -> str:
    if valor is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(valor).strip().lower())
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return " ".join(_TOKEN_RE.findall(texto))


def tokens_objeto(valor) -> tuple[str, ...]:
    texto = normalizar_texto_objeto(valor)
    tokens = []
    for token in texto.split():
        if token in STOPWORDS:
            continue
        token = SYNONYMS.get(token, token)
        if token in STOPWORDS:
            continue
        tokens.append(token)
    return tuple(tokens)


def firma_objeto(valor, categoria_principal=None) -> str:
    """Devuelve una firma lexical estable y auditable.

    La firma usa el conjunto ordenado de tokens significativos, de modo que
    cambios menores de orden, vocablos genéricos y un conjunto pequeño de
    sinónimos controlados no separen objetos. Una equivalencia semántica más
    sofisticada debe calibrarse con datos CGR.
    """
    tokens = sorted(set(tokens_objeto(valor)))
    categoria = normalizar_texto_objeto(categoria_principal) or "sin_categoria"
    if not tokens:
        return f"{categoria}::__SIN_OBJETO__"
    return f"{categoria}::{'|'.join(tokens)}"
