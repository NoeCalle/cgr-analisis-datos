"""Regresiones de calidad estructural y relacional del contrato canónico."""

import sys
from pathlib import Path

import pandas as pd
import pytest
from pyspark.sql import SparkSession

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from core.data_quality import (
    validar_calidad_integrada_pandas,
    validar_calidad_integrada_spark,
)


@pytest.fixture(scope="module")
def spark():
    session = (
        SparkSession.builder.master("local[1]")
        .appName("test-cgr-data-quality")
        .config("spark.ui.showConsoleProgress", "false")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


def _datasets_pandas():
    return {
        "contracts": pd.DataFrame(
            {
                "id_contrato": ["C1", "C2"],
                "id_proveedor": ["P1", "P2"],
                "id_entidad": ["E1", "E1"],
                "id_funcionario": ["F1", "F2"],
                "monto": [100.0, 200.0],
            }
        ),
        "suppliers": pd.DataFrame({"id_proveedor": ["P1", "P2"]}),
        "entities": pd.DataFrame({"id_entidad": ["E1"]}),
        "officials": pd.DataFrame({"id_funcionario": ["F1", "F2"]}),
        "payments": pd.DataFrame(
            {
                "id_pago": ["PG1", "PG2"],
                "id_contrato": ["C1", "C2"],
            }
        ),
    }


def test_quality_pandas_acepta_claves_unicas_y_relaciones_validas():
    summary = validar_calidad_integrada_pandas(_datasets_pandas())
    assert summary["status"] == "ok"
    assert summary["domains"]["contracts"]["rows"] == 2
    assert all(
        rel["status"] == "ok" for rel in summary["foreign_keys"].values()
    )


def test_quality_pandas_rechaza_clave_primaria_duplicada():
    datasets = _datasets_pandas()
    datasets["contracts"].loc[1, "id_contrato"] = "C1"
    with pytest.raises(ValueError, match="claves duplicadas"):
        validar_calidad_integrada_pandas(datasets)


def test_quality_pandas_rechaza_clave_foranea_huerfana():
    datasets = _datasets_pandas()
    datasets["contracts"].loc[1, "id_proveedor"] = "P999"
    with pytest.raises(ValueError, match="claves huérfanas"):
        validar_calidad_integrada_pandas(datasets)


def test_quality_pandas_rechaza_identificador_vacio_y_monto_negativo():
    datasets = _datasets_pandas()
    datasets["contracts"].loc[0, "id_proveedor"] = "   "
    with pytest.raises(ValueError, match="identificadores vacíos"):
        validar_calidad_integrada_pandas(datasets)

    datasets = _datasets_pandas()
    datasets["contracts"].loc[0, "monto"] = -1.0
    with pytest.raises(ValueError, match="montos negativos"):
        validar_calidad_integrada_pandas(datasets)


def _datasets_spark(spark):
    return {
        "contracts": spark.createDataFrame(
            [("C1", "P1", "E1", "F1", 100.0), ("C2", "P2", "E1", "F2", 200.0)],
            ["id_contrato", "id_proveedor", "id_entidad", "id_funcionario", "monto"],
        ),
        "suppliers": spark.createDataFrame(
            [("P1",), ("P2",)], ["id_proveedor"]
        ),
        "entities": spark.createDataFrame([("E1",)], ["id_entidad"]),
        "officials": spark.createDataFrame(
            [("F1",), ("F2",)], ["id_funcionario"]
        ),
        "payments": spark.createDataFrame(
            [("PG1", "C1"), ("PG2", "C2")], ["id_pago", "id_contrato"]
        ),
    }


def test_quality_spark_acepta_integridad_y_retorna_conteos(spark):
    summary = validar_calidad_integrada_spark(_datasets_spark(spark))
    assert summary["status"] == "ok"
    assert summary["domains"]["contracts"]["rows"] == 2
    assert summary["domains"]["contracts"]["duplicate_excess_rows"] == 0
    assert all(
        rel["status"] == "ok" for rel in summary["foreign_keys"].values()
    )


def test_quality_spark_rechaza_duplicados_y_huerfanos(spark):
    datasets = _datasets_spark(spark)
    datasets["contracts"] = spark.createDataFrame(
        [("C1", "P1", "E1", "F1", 100.0), ("C1", "P2", "E1", "F2", 200.0)],
        ["id_contrato", "id_proveedor", "id_entidad", "id_funcionario", "monto"],
    )
    with pytest.raises(ValueError, match="claves duplicadas"):
        validar_calidad_integrada_spark(datasets)

    datasets = _datasets_spark(spark)
    datasets["contracts"] = spark.createDataFrame(
        [("C1", "P999", "E1", "F1", 100.0)],
        ["id_contrato", "id_proveedor", "id_entidad", "id_funcionario", "monto"],
    )
    with pytest.raises(ValueError, match="claves huérfanas"):
        validar_calidad_integrada_spark(datasets)


def test_quality_spark_rechaza_id_vacio_y_monto_negativo(spark):
    datasets = _datasets_spark(spark)
    datasets["contracts"] = spark.createDataFrame(
        [("C1", "   ", "E1", "F1", 100.0)],
        ["id_contrato", "id_proveedor", "id_entidad", "id_funcionario", "monto"],
    )
    with pytest.raises(ValueError, match="identificadores vacíos"):
        validar_calidad_integrada_spark(datasets)

    datasets = _datasets_spark(spark)
    datasets["contracts"] = spark.createDataFrame(
        [("C1", "P1", "E1", "F1", -10.0)],
        ["id_contrato", "id_proveedor", "id_entidad", "id_funcionario", "monto"],
    )
    with pytest.raises(ValueError, match="montos negativos"):
        validar_calidad_integrada_spark(datasets)
