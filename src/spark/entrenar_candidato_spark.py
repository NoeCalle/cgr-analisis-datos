"""TRAIN operacional Spark MLlib.

La ruta operacional acepta dos fronteras de ingesta:
- CSV/SQL Server: contrato pandas validado y adaptación explícita a Spark;
- spark_sql: DataFrame Spark nativo desde la fuente hasta MLlib, sin toPandas.

El resultado es siempre un candidate y nunca promueve automáticamente.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pandas as pd
from pyspark.ml.classification import RandomForestClassifier
from pyspark.sql import functions as F

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

from core.config import cargar_config
from ingestar_canonico import integrar, integrar_spark
from preprocesamiento import ajustar_estado_preprocesamiento
from registro_modelos import guardar_json_determinista, sha256_ruta
from spark.ajustar_preprocesamiento_spark import ajustar_estado_preprocesamiento_spark
from spark.modelo_favoritismo_spark import (
    FEATURES as FAV_FEATURES,
    construir_features_favoritismo,
    crear_sesion,
    vectorizar,
)
from spark.modelo_fraccionamiento_spark import (
    FEATURES as FRAC_FEATURES,
    aplicar_senal_interpretable,
    construir_features_ventana_desde_df,
    entrenar_modelos_kmeans,
)
from spark.preprocesamiento_serving_spark import (
    aplicar_preprocesamiento_congelado,
    pandas_a_spark,
)

DEFAULT_MANIFEST = Path("outputs/runtime/spark_model_candidates/candidate_manifest.json")
DEFAULT_NUM_TREES = 100
DEFAULT_MAX_DEPTH = 3
FAVORITISMO_MONTO_OPERACIONAL = "monto_capped"


def _fingerprint_dataframe(df: pd.DataFrame) -> str:
    normalized = df.copy()
    for col in normalized.columns:
        if pd.api.types.is_datetime64_any_dtype(normalized[col]):
            normalized[col] = normalized[col].dt.strftime("%Y-%m-%dT%H:%M:%S")
    return hashlib.sha256(
        normalized.to_csv(index=False, na_rep="<NA>").encode("utf-8")
    ).hexdigest()


def _fingerprint_spark_dataframe(df) -> str:
    """Fingerprint distribuido sin colectar filas al driver."""
    columns = sorted(df.columns)
    values = [F.coalesce(F.col(c).cast("string"), F.lit("<NA>")) for c in columns]
    hashed = df.select(
        F.xxhash64(*values).alias("_h1"),
        F.xxhash64(F.lit("cgr-spark-native-v1"), *values).alias("_h2"),
    )
    stats = hashed.agg(
        F.count(F.lit(1)).alias("rows"),
        F.sum(F.col("_h1").cast("decimal(38,0)")).cast("string").alias("sum_h1"),
        F.sum(F.col("_h2").cast("decimal(38,0)")).cast("string").alias("sum_h2"),
        F.min("_h1").alias("min_h1"),
        F.max("_h1").alias("max_h1"),
        F.min("_h2").alias("min_h2"),
        F.max("_h2").alias("max_h2"),
    ).first().asDict()
    payload = {
        "columns": columns,
        "schema": df.schema.jsonValue(),
        "stats": {k: (None if v is None else str(v)) for k, v in stats.items()},
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _parametros_favoritismo() -> tuple[int, int, str]:
    resumen = Path("outputs/spark_favoritismo_resumen.json")
    if resumen.exists():
        data = json.loads(resumen.read_text(encoding="utf-8"))
        cfg = data.get("mejor_configuracion", {})
        if "numTrees" in cfg and "maxDepth" in cfg:
            return int(cfg["numTrees"]), int(cfg["maxDepth"]), "spark_cv_summary"
    return DEFAULT_NUM_TREES, DEFAULT_MAX_DEPTH, "poc_default"


def _entrenar_rf_final(df_feat, num_trees: int, max_depth: int):
    n_pos = df_feat.filter(F.col("label") == 1).count()
    n_neg = df_feat.filter(F.col("label") == 0).count()
    if n_pos < 1 or n_neg < 1:
        raise ValueError(
            f"TRAIN Spark favoritismo requiere ambas clases: positivos={n_pos}, negativos={n_neg}."
        )
    n_total = n_pos + n_neg
    df_weighted = df_feat.withColumn(
        "peso",
        F.when(F.col("label") == 1, F.lit(n_total / (2 * n_pos))).otherwise(
            F.lit(n_total / (2 * n_neg))
        ),
    )
    df_vec = vectorizar(df_weighted)
    modelo = RandomForestClassifier(
        featuresCol="features",
        labelCol="label",
        weightCol="peso",
        seed=42,
        numTrees=int(num_trees),
        maxDepth=int(max_depth),
    ).fit(df_vec)
    return modelo, int(n_pos), int(n_total)


def entrenar(
    config_path: str | Path,
    manifest_path: str | Path = DEFAULT_MANIFEST,
) -> dict:
    config = cargar_config(config_path)
    if config.get("mode") != "training":
        raise ValueError("TRAIN Spark requiere una configuración con mode: training.")

    manifest_path = Path(manifest_path)
    candidate_dir = manifest_path.parent
    if candidate_dir.exists():
        shutil.rmtree(candidate_dir)
    candidate_dir.mkdir(parents=True, exist_ok=True)

    preprocessor_json = candidate_dir / "preprocesador_contratos.json"
    preprocessor_medians_dir = candidate_dir / "medianas_monto_por_objeto"
    fav_model_dir = candidate_dir / "modelo_favoritismo_rf"
    frac_model_dir = candidate_dir / "modelo_fraccionamiento_kmeans"
    frac_scaler_dir = candidate_dir / "scaler_fraccionamiento"

    spark = crear_sesion("cgr-train-spark-mllib-candidate", operational=True)
    spark_mode = spark.sparkContext.master
    spark.sparkContext.setLogLevel("ERROR")
    spark.sparkContext.addPyFile(str(SRC_DIR / "umbrales_normativos.py"))

    source_type = config["source"]["type"]
    spark_native = source_type == "spark_sql"
    try:
        if spark_native:
            datasets, integration_summary = integrar_spark(config, spark=spark)
            raw_spark = datasets["contracts"]
            requeridos = {"label_favoritismo", "label_fraccionamiento"}
            faltantes = requeridos - set(raw_spark.columns)
            if faltantes:
                raise ValueError(f"TRAIN Spark requiere ground truth canónico: {sorted(faltantes)}")
            estado = ajustar_estado_preprocesamiento_spark(
                raw_spark, medians_output_path=preprocessor_medians_dir
            )
            medianas_df = spark.read.parquet(str(preprocessor_medians_dir))
            data_fingerprint = _fingerprint_spark_dataframe(raw_spark)
            contracts_rows = int(integration_summary["domains"]["contracts"]["rows"])
            input_engine = "spark_native"
        else:
            datasets, integration_summary = integrar(config)
            contracts = datasets["contracts"]
            requeridos = {"label_favoritismo", "label_fraccionamiento"}
            faltantes = requeridos - set(contracts.columns)
            if faltantes:
                raise ValueError(f"TRAIN Spark requiere ground truth canónico: {sorted(faltantes)}")
            estado = ajustar_estado_preprocesamiento(contracts)
            data_fingerprint = _fingerprint_dataframe(contracts)
            contracts_rows = int(len(contracts))
            raw_spark = pandas_a_spark(spark, contracts)
            medianas_df = None
            input_engine = "pandas_adapter"

        guardar_json_determinista(preprocessor_json, estado)
        procesado = aplicar_preprocesamiento_congelado(
            raw_spark, estado, medianas_df=medianas_df
        )

        fav_features = construir_features_favoritismo(
            procesado,
            label_col="label_favoritismo",
            monto_col=FAVORITISMO_MONTO_OPERACIONAL,
        )
        num_trees, max_depth, parametros_fuente = _parametros_favoritismo()
        fav_model, fav_positives, fav_rows = _entrenar_rf_final(
            fav_features, num_trees, max_depth
        )
        fav_model.write().overwrite().save(str(fav_model_dir))

        frac_features = aplicar_senal_interpretable(
            construir_features_ventana_desde_df(
                procesado, label_col="label_fraccionamiento"
            )
        )
        frac_pred, frac_model, frac_scaler = entrenar_modelos_kmeans(frac_features)
        frac_rows = int(frac_pred.count())
        frac_positives = int(frac_pred.filter(F.col("label") == 1).count())
        frac_model.write().overwrite().save(str(frac_model_dir))
        frac_scaler.write().overwrite().save(str(frac_scaler_dir))
    finally:
        spark.stop()

    artifacts = {
        "preprocessor_json": {
            "path": preprocessor_json.as_posix(),
            "sha256": sha256_ruta(preprocessor_json),
            "kind": "file",
        },
        "favoritismo_model": {
            "path": fav_model_dir.as_posix(),
            "sha256": sha256_ruta(fav_model_dir),
            "kind": "spark_model_directory",
        },
        "fraccionamiento_model": {
            "path": frac_model_dir.as_posix(),
            "sha256": sha256_ruta(frac_model_dir),
            "kind": "spark_model_directory",
        },
        "fraccionamiento_scaler": {
            "path": frac_scaler_dir.as_posix(),
            "sha256": sha256_ruta(frac_scaler_dir),
            "kind": "spark_model_directory",
        },
    }
    if spark_native:
        artifacts["preprocessor_medians"] = {
            "path": preprocessor_medians_dir.as_posix(),
            "sha256": sha256_ruta(preprocessor_medians_dir),
            "kind": "spark_parquet_directory",
        }

    identity = {
        "training_data": data_fingerprint,
        "preprocessor": artifacts["preprocessor_json"]["sha256"],
        "preprocessor_medians": artifacts.get("preprocessor_medians", {}).get("sha256"),
        "fav_model": artifacts["favoritismo_model"]["sha256"],
        "fav_amount_source": FAVORITISMO_MONTO_OPERACIONAL,
        "frac_model": artifacts["fraccionamiento_model"]["sha256"],
        "frac_scaler": artifacts["fraccionamiento_scaler"]["sha256"],
        "fav_params": {"numTrees": num_trees, "maxDepth": max_depth},
        "frac_params": {"k": int(frac_model.getK())},
    }
    candidate_hash = hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    manifest = {
        "schema_version": 1,
        "status": "candidate",
        "engine": "spark_mllib",
        "candidate_id": f"spark-poc-{candidate_hash[:16]}",
        "nature": "candidato Spark MLlib del PoC; no aprobado para infraestructura CGR",
        "training": {
            "config": str(config_path),
            "source_type": integration_summary["source_type"],
            "input_engine": input_engine,
            "spark_native_ingestion": spark_native,
            "pandas_materialization": not spark_native,
            "training_data_fingerprint_sha256": data_fingerprint,
            "contracts_rows": contracts_rows,
            "favoritismo_rows": fav_rows,
            "favoritismo_positives": fav_positives,
            "favoritismo_amount_source": FAVORITISMO_MONTO_OPERACIONAL,
            "fraccionamiento_rows": frac_rows,
            "fraccionamiento_positives": frac_positives,
            "fraccionamiento_amount_source": "monto",
            "ground_truth_required": True,
            "engine": "Apache Spark MLlib",
            "spark_mode": spark_mode,
            "preprocessing_contract": "corrected_frozen_json_v1",
            "validation_evidence": [
                "outputs/spark_favoritismo_resumen.json",
                "outputs/spark_fraccionamiento_resumen.json",
                "outputs/comparacion_modelos_favoritismo.json",
                "outputs/tuning_fraccionamiento_resumen.json",
            ],
        },
        "models": {
            "favoritismo": {
                "framework": "Apache Spark MLlib",
                "algorithm": "RandomForestClassificationModel",
                "features": FAV_FEATURES,
                "amount_source": FAVORITISMO_MONTO_OPERACIONAL,
                "label": "label_favoritismo",
                "params": {
                    "numTrees": num_trees,
                    "maxDepth": max_depth,
                    "selection_source": parametros_fuente,
                },
            },
            "fraccionamiento": {
                "framework": "Apache Spark MLlib",
                "algorithm": "StandardScalerModel + KMeansModel + distancia al centroide",
                "features": FRAC_FEATURES,
                "amount_source": "monto",
                "label": "label_fraccionamiento",
                "params": {"k": int(frac_model.getK())},
            },
        },
        "artifacts": artifacts,
    }
    guardar_json_determinista(manifest_path, manifest)
    print(f"Candidate Spark generado: {manifest['candidate_id']}")
    print(f"Manifest: {manifest_path}")
    print("Estado: candidate. Registry/champion no modificados.")
    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Entrena candidate Spark MLlib con preprocesamiento corregido; no promueve."
    )
    parser.add_argument("--config", default="config/local-training.yaml")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    entrenar(args.config, args.manifest)


if __name__ == "__main__":
    main()
