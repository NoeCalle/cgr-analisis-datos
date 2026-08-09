"""Regresiones del master Spark para TRAIN/INFERENCE operacional."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_helper_spark_distingue_legacy_y_operacional():
    source = _source("src/spark/modelo_favoritismo_spark.py")
    assert "operational: bool = False" in source
    assert "CGR_SPARK_MASTER" in source
    assert "CGR_SPARK_SHUFFLE_PARTITIONS" in source
    # La reproducción histórica conserva su master local determinístico.
    assert 'builder.master("local[*]")' in source


def test_train_usa_sesion_operacional_y_registra_master_real():
    source = _source("src/spark/entrenar_candidato_spark.py")
    assert 'crear_sesion("cgr-train-spark-mllib-candidate", operational=True)' in source
    assert "spark_mode = spark.sparkContext.master" in source
    assert '"spark_mode": spark_mode' in source


def test_inference_usa_sesion_operacional_y_registra_master_real():
    source = _source("src/spark/score_inference_spark.py")
    assert 'crear_sesion("cgr-inference-spark-mllib", operational=True)' in source
    assert "spark_mode = spark.sparkContext.master" in source
    assert '"spark_mode": spark_mode' in source
    assert '"spark_mode": "local[*]"' not in source
