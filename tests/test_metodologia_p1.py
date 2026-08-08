"""Pruebas de regresión para correcciones metodológicas P1/Sprint A."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from autoevaluacion import UMBRAL_RECALL_MINIMO, dividir_lote_para_reentrenamiento
from generar_diccionario_diagrama import DICCIONARIO
from preprocesamiento import codificar_y_normalizar, features_favoritismo


def test_contratacion_directa_y_comparacion_precios_son_features_distintas():
    df = pd.DataFrame([
        {
            "id_contrato": "C1", "id_proveedor": "P1", "id_entidad": "E1",
            "id_funcionario": "F1", "modalidad": "Contratación Directa",
            "objeto": "Bien", "monto": 100.0, "monto_capped": 100.0,
            "fecha_contrato": pd.Timestamp("2024-01-01"), "es_favoritismo_real": False,
        },
        {
            "id_contrato": "C2", "id_proveedor": "P1", "id_entidad": "E1",
            "id_funcionario": "F1", "modalidad": "Comparación de Precios",
            "objeto": "Bien", "monto": 100.0, "monto_capped": 100.0,
            "fecha_contrato": pd.Timestamp("2024-01-02"), "es_favoritismo_real": False,
        },
        {
            "id_contrato": "C3", "id_proveedor": "P1", "id_entidad": "E1",
            "id_funcionario": "F1", "modalidad": "Licitación Pública",
            "objeto": "Bien", "monto": 100.0, "monto_capped": 100.0,
            "fecha_contrato": pd.Timestamp("2024-01-03"), "es_favoritismo_real": False,
        },
    ])

    procesado = codificar_y_normalizar(df)
    feat = features_favoritismo(procesado).iloc[0]

    assert feat["pct_contratacion_directa"] == 1 / 3
    assert feat["pct_comparacion_precios"] == 1 / 3
    assert "pct_no_competitiva" not in feat.index


def test_holdout_reentrenamiento_no_se_superpone_con_nuevo_train():
    filas = []
    for i in range(20):
        filas.append({
            "label_favoritismo_real": i < 4,
            "dummy": i,
        })
    df = pd.DataFrame(filas)

    nuevo_train, holdout = dividir_lote_para_reentrenamiento(df)

    assert holdout is not None
    assert set(nuevo_train.index).isdisjoint(set(holdout.index))
    assert set(nuevo_train.index) | set(holdout.index) == set(df.index)


def test_umbral_recall_es_absoluto_y_explicito():
    assert UMBRAL_RECALL_MINIMO == 0.80


def test_diccionario_no_reintroduce_nombres_obsoletos():
    texto = " ".join(str(valor) for fila in DICCIONARIO for valor in fila).lower()

    assert "pct_no_competitiva" not in texto
    assert "cumple_regla_fraccionamiento" not in texto
    assert "s/. 400,000" not in texto
    assert "pct_contratacion_directa" in texto
    assert "pct_comparacion_precios" in texto
    assert "senal_priorizacion_fraccionamiento" in texto
