from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from generar_pagos_sinteticos import generar_pagos
from preprocesamiento import features_favoritismo
from umbrales_normativos import (
    FUENTES_NORMATIVAS,
    clasificar_modalidad_frente_regimen,
    obtener_procedimiento_referencial_por_cuantia,
)


def test_procedimiento_referencial_respeta_cambio_22_abril_2025():
    assert obtener_procedimiento_referencial_por_cuantia(
        "2025-04-21", 100_000, categoria_principal="goods"
    ) == "Adjudicación Simplificada"
    assert obtener_procedimiento_referencial_por_cuantia(
        "2025-04-22", 100_000, categoria_principal="goods"
    ) == "Licitación Pública Abreviada"
    assert obtener_procedimiento_referencial_por_cuantia(
        "2025-04-22", 100_000, categoria_principal="services"
    ) == "Concurso Público Abreviado"
    assert obtener_procedimiento_referencial_por_cuantia(
        "2026-02-10", 5_500_000, categoria_principal="works"
    ) == "Licitación Pública"


def test_modalidades_especiales_no_se_declaran_incompatibles_solo_por_cuantia():
    out = clasificar_modalidad_frente_regimen(
        "2026-02-10",
        120_000,
        "Contratación Directa",
        categoria_principal="goods",
    )
    assert out["clasificacion"] == "especial_no_inferible_por_cuantia"
    assert out["procedimiento_referencial"] == "Licitación Pública Abreviada"


def test_procedencia_normativa_versionada_2023_2026():
    assert set(range(2023, 2027)) <= set(FUENTES_NORMATIVAS)
    for anio in range(2023, 2027):
        fuente = FUENTES_NORMATIVAS[anio]
        urls = [v for k, v in fuente.items() if k.startswith("url_")]
        assert urls
        assert all(url.startswith("https://www.gob.pe/") for url in urls)


def test_pagos_sinteticos_mantienen_integridad_referencial_y_montos_no_negativos():
    contratos = pd.DataFrame(
        {
            "id_contrato": [f"C{i:05d}" for i in range(600)],
            "fecha_contrato": pd.date_range("2024-01-01", periods=600, freq="D"),
            "monto": [100_000 + i * 100 for i in range(600)],
        }
    )
    pagos = generar_pagos(contratos)
    assert len(pagos) >= len(contratos)
    assert set(pagos["id_contrato"]) <= set(contratos["id_contrato"])
    assert pagos["id_pago"].is_unique
    assert (pagos["monto_devengado"] >= 0).all()
    assert (pagos["monto_pagado"] >= 0).all()
    assert {"completo", "parcial", "demorado", "pendiente"} <= set(pagos["escenario_sintetico"])


def test_favoritismo_puede_consumir_monto_capado_sin_cambiar_nombres_de_features():
    df = pd.DataFrame(
        {
            "id_contrato": ["C1", "C2"],
            "id_proveedor": ["P1", "P1"],
            "id_entidad": ["E1", "E1"],
            "id_funcionario": ["F1", "F1"],
            "objeto": ["Bien", "Bien"],
            "fecha_contrato": pd.to_datetime(["2026-01-01", "2026-02-01"]),
            "monto": [100.0, 1000.0],
            "monto_capped": [100.0, 200.0],
            "es_contratacion_directa": [False, False],
            "es_comparacion_precios": [False, False],
        }
    )
    raw = features_favoritismo(df, label_col=None, monto_col="monto")
    robusto = features_favoritismo(df, label_col=None, monto_col="monto_capped")
    assert raw.loc[0, "monto_total"] == 1100.0
    assert robusto.loc[0, "monto_total"] == 300.0
    assert set(raw.columns) == set(robusto.columns)


def test_rutas_operacionales_declaran_monto_capado_y_benchmark_queda_separado():
    root = Path(__file__).resolve().parents[1]
    sklearn_train = (root / "src/entrenar_candidatos.py").read_text(encoding="utf-8")
    sklearn_score = (root / "src/score_inference.py").read_text(encoding="utf-8")
    spark_train = (root / "src/spark/entrenar_candidato_spark.py").read_text(encoding="utf-8")
    spark_score = (root / "src/spark/score_inference_spark.py").read_text(encoding="utf-8")
    preprocesamiento = (root / "src/preprocesamiento.py").read_text(encoding="utf-8")

    rutas_operacionales = [sklearn_train, sklearn_score, spark_train, spark_score]
    for texto in rutas_operacionales:
        assert 'FAVORITISMO_MONTO_OPERACIONAL = "monto_capped"' in texto
        assert "limpiar_e_imputar" not in texto

    # El helper del benchmark sigue disponible para reproducibilidad, pero las
    # rutas operacionales usan el contrato FIT/TRANSFORM explícito.
    assert "def limpiar_e_imputar" in preprocesamiento
    assert "def preparar_para_features_entrenamiento" in preprocesamiento
    assert "def preparar_para_features_inferencia" in preprocesamiento
    assert 'monto_col: str = "monto"' in preprocesamiento
