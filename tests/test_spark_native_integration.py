"""Regresiones Sprint 5: spark_sql debe permanecer Spark-native."""

import sys
from pathlib import Path

import pytest
from pyspark.sql import DataFrame, SparkSession

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.config import validar_config
from ingestar_canonico import integrar, integrar_spark
from spark.ajustar_preprocesamiento_spark import ajustar_estado_preprocesamiento_spark
from spark.preprocesamiento_serving_spark import aplicar_preprocesamiento_congelado


@pytest.fixture(scope="module")
def spark():
    session = (
        SparkSession.builder.master("local[1]")
        .appName("test-cgr-spark-native")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


def _mapping(include_labels=False):
    mapping = {
        "id_contrato": "NRO_CONTRATO",
        "id_proveedor": "COD_PROV",
        "id_entidad": "SEC_EJEC",
        "monto": "IMP_ADJ",
        "fecha_contrato": "FEC_SUSC",
        "modalidad": "TIP_PROC",
        "objeto": "DESC_OBJ",
        "categoria_principal": "CAT_PRINC",
    }
    if include_labels:
        mapping["label_favoritismo"] = "GT_FAV"
        mapping["label_fraccionamiento"] = "GT_FRAC"
    return mapping


def _config(view, *, training=False):
    return {
        "mode": "training" if training else "inference",
        "source": {"type": "spark_sql", "tables": {"contracts": view}},
        "mapping": {"contracts": _mapping(training)},
    }


def test_spark_sql_mapping_validacion_y_preprocesamiento_no_materializan_pandas(spark, tmp_path):
    rows = [
        ("X-001", "000123", "ENT-1", "125000.50", "2026-07-01", "Licitación Pública", "Bien A", "goods"),
        ("X-002", "SUP-8", "ENT-1", None, "2026-07-03", None, "Bien A", "goods"),
        ("X-003", "SUP-8", "ENT-2", "98000.00", "2026-07-05", "Contratación Directa", None, None),
    ]
    physical = spark.createDataFrame(
        rows,
        [
            "NRO_CONTRATO", "COD_PROV", "SEC_EJEC", "IMP_ADJ", "FEC_SUSC",
            "TIP_PROC", "DESC_OBJ", "CAT_PRINC",
        ],
    )
    view = "vw_test_contracts_spark_native"
    physical.createOrReplaceTempView(view)
    config = _config(view)
    validar_config(config)

    datasets, summary = integrar_spark(config, spark=spark)
    contracts = datasets["contracts"]

    assert isinstance(contracts, DataFrame)
    assert summary["native_engine"] == "spark"
    assert summary["domains"]["contracts"]["rows"] == 3
    assert contracts.schema["monto"].dataType.simpleString() == "double"
    assert contracts.schema["fecha_contrato"].dataType.simpleString() == "timestamp"
    assert contracts.where("id_proveedor = '000123'").count() == 1

    medians_path = tmp_path / "medianas_objeto"
    estado = ajustar_estado_preprocesamiento_spark(
        contracts, medians_output_path=medians_path
    )
    assert estado["fit_engine"] == "spark"
    assert estado["monto_mediana_por_objeto_external"] is True
    assert estado["monto_mediana_por_objeto"] == {}
    medianas_df = spark.read.parquet(str(medians_path))
    assert {"objeto", "monto_mediana"} == set(medianas_df.columns)

    transformed = aplicar_preprocesamiento_congelado(
        contracts, estado, medianas_df=medianas_df
    )
    assert transformed.where("monto is null").count() == 0
    assert transformed.where("modalidad is null").count() == 0
    assert "monto_capped" in transformed.columns


def test_spark_sql_training_con_labels_booleanos(spark):
    rows = [
        ("C1", "P1", "E1", 100.0, "2026-01-01", "Licitación Pública", "A", "goods", 0, 0),
        ("C2", "P1", "E1", 200.0, "2026-01-02", "Licitación Pública", "A", "goods", 1, 0),
        ("C3", "P2", "E2", 90.0, "2026-01-03", "Contratación Directa", "B", "services", 0, 1),
    ]
    view = "vw_test_training_spark_native"
    spark.createDataFrame(
        rows,
        [
            "NRO_CONTRATO", "COD_PROV", "SEC_EJEC", "IMP_ADJ", "FEC_SUSC",
            "TIP_PROC", "DESC_OBJ", "CAT_PRINC", "GT_FAV", "GT_FRAC",
        ],
    ).createOrReplaceTempView(view)
    config = _config(view, training=True)
    validar_config(config)

    datasets, _ = integrar_spark(config, spark=spark)
    contracts = datasets["contracts"]
    assert contracts.schema["label_favoritismo"].dataType.simpleString() == "boolean"
    assert contracts.schema["label_fraccionamiento"].dataType.simpleString() == "boolean"
    assert contracts.where("label_favoritismo = true").count() == 1
    assert contracts.where("label_fraccionamiento = true").count() == 1


def test_spark_sql_rechaza_monto_fisico_no_convertible(spark):
    view = "vw_test_invalid_amount_spark_native"
    spark.createDataFrame(
        [("C1", "P1", "E1", "NO_ES_NUMERO", "2026-01-01", "Licitación Pública", "A", "goods")],
        [
            "NRO_CONTRATO", "COD_PROV", "SEC_EJEC", "IMP_ADJ", "FEC_SUSC",
            "TIP_PROC", "DESC_OBJ", "CAT_PRINC",
        ],
    ).createOrReplaceTempView(view)

    with pytest.raises(ValueError, match="monto"):
        integrar_spark(_config(view), spark=spark)


def test_integracion_pandas_rechaza_spark_sql_para_evitar_collect_implicito():
    config = _config("vista_no_necesita_existir")
    with pytest.raises(ValueError, match="Spark-native"):
        integrar(config)


def test_ruta_operacional_spark_no_contiene_to_pandas_y_serving_no_hace_fit():
    connector = (ROOT / "src" / "connectors" / "spark_sql.py").read_text(encoding="utf-8")
    train = (ROOT / "src" / "spark" / "entrenar_candidato_spark.py").read_text(encoding="utf-8")
    inference = (ROOT / "src" / "spark" / "score_inference_spark.py").read_text(encoding="utf-8")
    serving = (ROOT / "src" / "spark" / "preprocesamiento_serving_spark.py").read_text(encoding="utf-8")

    assert ".toPandas(" not in connector
    assert ".toPandas(" not in train
    assert ".toPandas(" not in inference
    assert "integrar_spark(config, spark=spark)" in train
    assert "integrar_spark(config, spark=spark)" in inference
    assert "ajustar_estado_preprocesamiento" not in serving
    assert ".fit(" not in serving
