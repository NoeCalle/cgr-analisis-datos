"""Benchmark parametrizable de la ruta operacional Spark.

Mide integración, FIT/TRANSFORM y feature engineering sobre la fuente indicada
por configuración. No reemplaza pruebas de carga/aceptación en infraestructura
CGR: el JSON registra explícitamente motor, master, filas y naturaleza de la
corrida para evitar presentar un smoke local como evidencia productiva.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from core.config import cargar_config
from core.fingerprints import fingerprint_pandas_dataframe, fingerprint_spark_dataframe
from ingestar_canonico import integrar, integrar_spark
from spark.ajustar_preprocesamiento_spark import ajustar_estado_preprocesamiento_spark
from spark.modelo_favoritismo_spark import construir_features_favoritismo, crear_sesion
from spark.modelo_fraccionamiento_spark import construir_features_ventana_desde_df
from spark.preprocesamiento_serving_spark import aplicar_preprocesamiento_congelado, pandas_a_spark

DEFAULT_OUTPUT = Path("outputs/benchmark_spark_operacional.json")
DEFAULT_RUNTIME = Path("outputs/runtime/benchmark_spark")


def _stats(values: list[float]) -> dict:
    return {
        "min_s": float(min(values)),
        "median_s": float(statistics.median(values)),
        "max_s": float(max(values)),
        "mean_s": float(statistics.fmean(values)),
    }


def ejecutar(config_path: str, repetitions: int = 3, output_path: str | Path = DEFAULT_OUTPUT) -> dict:
    if repetitions < 1:
        raise ValueError("repetitions debe ser >= 1")

    config = cargar_config(config_path)
    source_type = config["source"]["type"]
    spark = crear_sesion("cgr-benchmark-operacional", operational=True)
    spark.sparkContext.setLogLevel("ERROR")
    spark.sparkContext.addPyFile(str(Path(__file__).resolve().parents[1] / "core" / "objeto_similarity.py"))
    spark.sparkContext.addPyFile(str(Path(__file__).resolve().parents[1] / "umbrales_normativos.py"))
    try:
        t0 = time.perf_counter()
        if source_type == "spark_sql":
            datasets, integration_summary = integrar_spark(config, spark=spark)
            raw = datasets["contracts"]
            fingerprint = fingerprint_spark_dataframe(raw)
            input_engine = "spark_native"
            pandas_materialization = False
        else:
            datasets, integration_summary = integrar(config)
            pdf = datasets["contracts"]
            fingerprint = fingerprint_pandas_dataframe(pdf)
            raw = pandas_a_spark(spark, pdf)
            input_engine = "pandas_adapter"
            pandas_materialization = True
        integration_s = time.perf_counter() - t0

        rows = int(raw.count())
        medians_path = DEFAULT_RUNTIME / "medianas_monto_por_objeto"
        t_fit = time.perf_counter()
        state = ajustar_estado_preprocesamiento_spark(raw, medians_output_path=medians_path)
        medians = spark.read.parquet(str(medians_path))
        fit_s = time.perf_counter() - t_fit

        processed = aplicar_preprocesamiento_congelado(raw, state, medianas_df=medians).cache()
        processed.count()
        fav = construir_features_favoritismo(
            processed, label_col=None, monto_col="monto_capped"
        ).cache()
        frac = construir_features_ventana_desde_df(processed, label_col=None).cache()

        iteration_times = []
        fav_groups = frac_groups = 0
        try:
            for _ in range(repetitions):
                start = time.perf_counter()
                fav_groups = int(fav.count())
                frac_groups = int(frac.count())
                iteration_times.append(time.perf_counter() - start)
        finally:
            fav.unpersist()
            frac.unpersist()
            processed.unpersist()

        stats = _stats(iteration_times)
        median_s = stats["median_s"]
        payload = {
            "schema_version": 1,
            "scope": "benchmark_operacional_spark_parametrizable",
            "config": str(config_path),
            "source_type": source_type,
            "input_engine": input_engine,
            "spark_native_ingestion": source_type == "spark_sql",
            "pandas_materialization": pandas_materialization,
            "spark_master": spark.sparkContext.master,
            "spark_version": spark.version,
            "shuffle_partitions": spark.conf.get("spark.sql.shuffle.partitions"),
            "training_data_fingerprint_sha256": fingerprint,
            "rows_contracts": rows,
            "favoritismo_groups": fav_groups,
            "fraccionamiento_groups": frac_groups,
            "repetitions": repetitions,
            "timings": {
                "integration_s": float(integration_s),
                "distributed_preprocessor_fit_s": float(fit_s),
                "feature_actions": stats,
                "contracts_rows_per_second_on_median_feature_action": (
                    float(rows / median_s) if median_s > 0 else None
                ),
            },
            "integration_rows": int(integration_summary["domains"]["contracts"]["rows"]),
            "institutional_acceptance": False,
            "notice": (
                "Benchmark técnico parametrizable. Sus resultados describen únicamente el entorno "
                "donde se ejecutó y no sustituyen pruebas de carga, robustez, concurrencia, skew, "
                "DEV/QA/PROD ni criterios de aceptación de la CGR."
            ),
        }
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return payload
    finally:
        spark.stop()


def main():
    parser = argparse.ArgumentParser(description="Benchmark parametrizable de la ruta operacional Spark.")
    parser.add_argument("--config", default="config/local.yaml")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    ejecutar(args.config, args.repetitions, args.output)


if __name__ == "__main__":
    main()
