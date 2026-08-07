"""Pruebas de regresión del motor normativo de señales de fraccionamiento."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from umbrales_normativos import (
    es_categoria_obra,
    obtener_contexto_normativo,
    obtener_regimen,
    obtener_umbral,
)


def test_topes_verificados_2022_2026():
    assert obtener_umbral("2022-06-01", categoria_principal="goods") == 400_000
    assert obtener_umbral("2022-06-01", categoria_principal="works") == 2_800_000
    assert obtener_umbral("2023-06-01", categoria_principal="services") == 480_000
    assert obtener_umbral("2023-06-01", categoria_principal="works") == 2_800_000
    assert obtener_umbral("2024-06-01", categoria_principal="goods") == 480_000
    assert obtener_umbral("2024-06-01", categoria_principal="works") == 2_800_000
    assert obtener_umbral("2025-06-01", categoria_principal="goods") == 485_000
    assert obtener_umbral("2025-06-01", categoria_principal="works") == 5_000_000
    assert obtener_umbral("2026-06-01", categoria_principal="services") == 485_000
    assert obtener_umbral("2026-06-01", categoria_principal="works") == 5_000_000


def test_cambio_de_regimen_22_abril_2025():
    assert obtener_regimen("2025-04-21") == "Ley 30225"
    assert obtener_regimen("2025-04-22") == "Ley 32069"


def test_categoria_odcs_tiene_prioridad_sobre_texto_libre():
    # El texto contiene "infraestructura", pero OCDS dice explícitamente service.
    assert not es_categoria_obra(
        "Servicio de mantenimiento de infraestructura",
        categoria_principal="services",
    )
    # Y si OCDS declara works, esa clasificación prevalece incluso con texto pobre.
    assert es_categoria_obra("Mantenimiento general", categoria_principal="works")


def test_fallback_textual_es_conservador():
    assert not es_categoria_obra("Servicio de mantenimiento de infraestructura")
    assert es_categoria_obra("Obra de rehabilitación vial")


def test_anio_no_parametrizado_falla_en_vez_de_aproximar():
    with pytest.raises(ValueError):
        obtener_umbral("2027-01-01", categoria_principal="goods")


def test_contexto_normativo_es_auditable():
    ctx = obtener_contexto_normativo("2026-01-15", categoria_principal="works")
    assert ctx["regimen"] == "Ley 32069"
    assert ctx["categoria_umbral"] == "obras"
    assert ctx["umbral"] == 5_000_000
    assert "Abreviada" in ctx["procedimiento_referencial"]
