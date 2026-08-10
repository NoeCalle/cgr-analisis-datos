"""Regresiones metodológicas de la Etapa 2B."""

import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml
from pyspark.sql import SparkSession

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from autoevaluacion_champion import _crear_config_retraining
from core.objeto_similarity import firma_objeto
from preprocesamiento import features_fraccionamiento
from spark.modelo_fraccionamiento_spark import construir_features_ventana_desde_df


@pytest.fixture(scope="module")
def spark():
    session = (
        SparkSession.builder.master("local[1]")
        .appName("test-cgr-metodologia-2b")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    session.sparkContext.addPyFile(str(ROOT / "src" / "core" / "objeto_similarity.py"))
    session.sparkContext.addPyFile(str(ROOT / "src" / "umbrales_normativos.py"))
    yield session
    session.stop()


def test_firma_objeto_agrupa_variantes_controladas():
    assert firma_objeto(
        "Servicio de mantenimiento de infraestructura", "services"
    ) == firma_objeto(
        "Servicio de conservación preventiva de infraestructura", "services"
    )
    assert firma_objeto(
        "Obra de rehabilitación vial", "works"
    ) == firma_objeto(
        "Rehabilitación de vía pública", "works"
    )
    assert firma_objeto(
        "Adquisición de equipos informáticos", "goods"
    ) == firma_objeto(
        "Compra de equipos informáticos", "goods"
    )


def _ventanas_fixture():
    # La ventana del 1/ene tiene 3 contratos por S/ 300; la del 20/ene tiene
    # solo 2 pero suma S/ 1,800. El feature correcto debe reportar 3 y 300,
    # nunca combinar 3 con 1,800.
    return pd.DataFrame([
        {"id_contrato": "C1", "id_proveedor": "P1", "id_entidad": "E1", "objeto": "Servicio de mantenimiento de infraestructura", "categoria_principal": "services", "fecha_contrato": pd.Timestamp("2024-01-01"), "monto": 100.0},
        {"id_contrato": "C2", "id_proveedor": "P1", "id_entidad": "E1", "objeto": "Servicio de conservación preventiva de infraestructura", "categoria_principal": "services", "fecha_contrato": pd.Timestamp("2024-01-05"), "monto": 100.0},
        {"id_contrato": "C3", "id_proveedor": "P1", "id_entidad": "E1", "objeto": "Mantenimiento preventivo de infraestructura", "categoria_principal": "services", "fecha_contrato": pd.Timestamp("2024-01-10"), "monto": 100.0},
        {"id_contrato": "C4", "id_proveedor": "P1", "id_entidad": "E1", "objeto": "Servicio de mantenimiento de infraestructura", "categoria_principal": "services", "fecha_contrato": pd.Timestamp("2024-01-20"), "monto": 900.0},
        {"id_contrato": "C5", "id_proveedor": "P1", "id_entidad": "E1", "objeto": "Servicio de conservación preventiva de infraestructura", "categoria_principal": "services", "fecha_contrato": pd.Timestamp("2024-01-25"), "monto": 900.0},
    ])


def test_ventana_fraccionamiento_pandas_y_spark_tienen_misma_semantica(spark):
    pdf = _ventanas_fixture()
    pandas_feat = features_fraccionamiento(pdf, label_col=None).iloc[0]
    spark_feat = (
        construir_features_ventana_desde_df(spark.createDataFrame(pdf), label_col=None)
        .toPandas()
        .iloc[0]
    )
    assert pandas_feat["objeto_familia"] == spark_feat["objeto_familia"]
    assert int(pandas_feat["max_contratos_ventana_15d"]) == 3
    assert int(spark_feat["max_contratos_ventana_15d"]) == 3
    assert float(pandas_feat["monto_total_ventana_15d"]) == pytest.approx(300.0)
    assert float(spark_feat["monto_total_ventana_15d"]) == pytest.approx(300.0)


def test_config_retraining_mapea_csv_canonico(tmp_path):
    base = yaml.safe_load((ROOT / "config" / "local-training.yaml").read_text(encoding="utf-8"))
    target = tmp_path / "training.yaml"
    _crear_config_retraining(base, tmp_path / "contracts.csv", target)
    cfg = yaml.safe_load(target.read_text(encoding="utf-8"))
    mapping = cfg["mapping"]["contracts"]
    assert mapping["label_favoritismo"] == "label_favoritismo"
    assert mapping["label_fraccionamiento"] == "label_fraccionamiento"
    assert mapping["categoria_principal"] == "categoria_principal"


def test_scripts_operacionales_declaran_evidencia_correcta():
    fav = (ROOT / "src" / "spark" / "evaluar_favoritismo_spark.py").read_text(encoding="utf-8")
    frac = (ROOT / "src" / "spark" / "evaluar_fraccionamiento_spark.py").read_text(encoding="utf-8")
    train = (ROOT / "src" / "spark" / "entrenar_candidato_spark.py").read_text(encoding="utf-8")
    assert 'AMOUNT_SOURCE = "monto_capped"' in fav
    assert "tuning_favoritismo_spark_resumen.json" in train
    assert "tuning_fraccionamiento_spark_resumen.json" in train
    assert "holdout" in fav.lower()
    assert "holdout" in frac.lower()


def test_clis_historicos_favoritismo_delegan_al_evaluador_operacional():
    for rel in ["src/tuning_favoritismo.py", "src/comparar_modelos_favoritismo.py"]:
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert "evaluar_favoritismo_operacional" in source
        assert "entrada_plata" not in source
        assert "dataset_favoritismo.csv" not in source
