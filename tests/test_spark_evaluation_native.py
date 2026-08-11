"""Regresiones Etapa 5B: evaluación/tuning spark_sql debe ser Spark-native."""

import sys
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.fingerprints import fingerprint_spark_dataframe
from spark.evaluar_favoritismo_spark import (
    _metricas_holdout_spark,
    _split_raw_contracts_spark,
)
from spark.evaluar_fraccionamiento_spark import (
    _metricas_spark,
    _split_raw_spark,
    _validation_split_spark,
)


@pytest.fixture(scope="module")
def spark():
    session = (
        SparkSession.builder.master("local[1]")
        .appName("test-cgr-spark-evaluation-native")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    session.sparkContext.addPyFile(str(ROOT / "src" / "core" / "objeto_similarity.py"))
    yield session
    session.stop()


def _contracts_favoritismo(spark):
    rows = []
    for label in [0, 1]:
        for i in range(8):
            rows.append(
                (
                    f"C-{label}-{i}",
                    f"P-{label}-{i}",
                    "E-1",
                    float(100 + i),
                    "2026-01-01",
                    "Licitación Pública",
                    "Servicio de mantenimiento de infraestructura",
                    "services",
                    bool(label),
                )
            )
    return spark.createDataFrame(
        rows,
        [
            "id_contrato", "id_proveedor", "id_entidad", "monto", "fecha_contrato",
            "modalidad", "objeto", "categoria_principal", "label_favoritismo",
        ],
    )


def _contracts_fraccionamiento(spark):
    rows = []
    for label in [0, 1]:
        for i in range(8):
            rows.append(
                (
                    f"CF-{label}-{i}",
                    f"PF-{label}-{i}",
                    "E-1",
                    float(80 + i),
                    "2026-01-01",
                    "Adjudicación Simplificada",
                    "Servicio de mantenimiento de infraestructura",
                    "services",
                    bool(label),
                )
            )
    return spark.createDataFrame(
        rows,
        [
            "id_contrato", "id_proveedor", "id_entidad", "monto", "fecha_contrato",
            "modalidad", "objeto", "categoria_principal", "label_fraccionamiento",
        ],
    )


def test_split_favoritismo_es_distribuido_y_deterministico(spark):
    df = _contracts_favoritismo(spark)
    before = fingerprint_spark_dataframe(df)
    dev, holdout = _split_raw_contracts_spark(df)
    assert dev.count() + holdout.count() == df.count()
    assert holdout.select("id_proveedor", "id_entidad").distinct().count() == 4
    assert set(r[0] for r in holdout.select("label_favoritismo").distinct().collect()) == {False, True}
    assert fingerprint_spark_dataframe(df) == before


def test_split_fraccionamiento_es_distribuido_y_deterministico(spark):
    df = _contracts_fraccionamiento(spark)
    dev, holdout = _split_raw_spark(df)
    assert dev.count() + holdout.count() == df.count()
    assert holdout.select("id_proveedor", "id_entidad").distinct().count() == 4
    assert set(r[0] for r in holdout.select("label_fraccionamiento").distinct().collect()) == {False, True}


def test_metricas_favoritismo_no_requieren_pandas(spark):
    scored = spark.createDataFrame(
        [(1, 0.95), (0, 0.80), (1, 0.70), (0, 0.10)],
        ["label", "score"],
    )
    m = _metricas_holdout_spark(scored)
    assert set(["accuracy", "auc_pr", "auc_roc", "precision", "recall", "f1", "recall_at_k"]) <= set(m)
    assert 0.0 <= m["recall_at_k"] <= 1.0


def test_metricas_fraccionamiento_y_validation_split_permanecen_spark(spark):
    scored = spark.createDataFrame(
        [(1, 0.95), (0, 0.80), (1, 0.70), (0, 0.10)],
        ["label", "score_anomalia"],
    )
    m = _metricas_spark(scored)
    assert 0.0 <= m["auc_pr"] <= 1.0

    rows = []
    for label in [0, 1]:
        for i in range(9):
            rows.append((f"P{label}-{i}", "E", f"F{label}-{i}", label, 3.0, 100.0, 0.8, 200.0))
    feat = spark.createDataFrame(
        rows,
        [
            "id_proveedor", "id_entidad", "objeto_familia", "label",
            "max_contratos_ventana_15d", "monto_total_ventana_15d",
            "pct_montos_bajo_umbral", "monto_total_objeto",
        ],
    )
    train, val = _validation_split_spark(feat, 11)
    assert train.count() + val.count() == feat.count()
    assert set(r[0] for r in val.select("label").distinct().collect()) == {0, 1}


def test_fuentes_de_evaluacion_no_reintroducen_materializacion_del_dataset():
    fav = (ROOT / "src" / "spark" / "evaluar_favoritismo_spark.py").read_text(encoding="utf-8")
    frac = (ROOT / "src" / "spark" / "evaluar_fraccionamiento_spark.py").read_text(encoding="utf-8")

    for source in [fav, frac]:
        assert ".toPandas(" not in source
        assert "integrar_spark(config, spark=spark)" in source
        assert "fingerprint_spark_dataframe" in source
        assert 'source_type == "spark_sql"' in source
        assert '"spark_native_evaluation": source_type == "spark_sql"' in source

    assert ".isin(" not in frac
