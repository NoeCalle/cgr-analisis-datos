"""TRAIN operacional Spark MLlib.

La ruta operacional acepta CSV/SQL Server mediante adaptador explícito y
``spark_sql`` de forma Spark-native. Los hiperparámetros se leen únicamente de
evaluaciones del MISMO pipeline operacional y, desde 3B, del MISMO corpus
(fingerprint canónico). El resultado siempre queda como candidate hasta una
promoción explícita.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

from pyspark.ml.classification import RandomForestClassifier
from pyspark.sql import functions as F

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

from core.config import cargar_config
from core.fingerprints import fingerprint_pandas_dataframe, fingerprint_spark_dataframe
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
DEFAULT_K = 2
FAVORITISMO_MONTO_OPERACIONAL = "monto_capped"
FAV_EVIDENCE = Path("outputs/tuning_favoritismo_spark_resumen.json")
FRAC_EVIDENCE = Path("outputs/tuning_fraccionamiento_spark_resumen.json")


def _leer_evidencia_para_corpus(path: Path, expected_fingerprint: str) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Falta evidencia operacional requerida para TRAIN: {path}. "
            "Ejecute la evaluación sobre el mismo corpus antes de entrenar."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    evidence_fingerprint = data.get("training_data_fingerprint_sha256")
    if evidence_fingerprint != expected_fingerprint:
        raise ValueError(
            f"Evidencia {path} pertenece a otro corpus: "
            f"evidence={evidence_fingerprint!r} train={expected_fingerprint!r}. "
            "No se reutilizan hiperparámetros de un dataset distinto."
        )
    return data


def _parametros_favoritismo(expected_fingerprint: str) -> tuple[int, int, str, dict]:
    data = _leer_evidencia_para_corpus(FAV_EVIDENCE, expected_fingerprint)
    cfg = data.get("mejor_configuracion", {})
    if "numTrees" not in cfg or "maxDepth" not in cfg:
        raise ValueError(f"Evidencia de favoritismo incompleta: {FAV_EVIDENCE}")
    evidence = {
        "path": FAV_EVIDENCE.as_posix(),
        "sha256": sha256_ruta(FAV_EVIDENCE),
        "training_data_fingerprint_sha256": expected_fingerprint,
    }
    return int(cfg["numTrees"]), int(cfg["maxDepth"]), "spark_operational_holdout", evidence


def _parametros_fraccionamiento(expected_fingerprint: str) -> tuple[int, str, dict]:
    data = _leer_evidencia_para_corpus(FRAC_EVIDENCE, expected_fingerprint)
    cfg = data.get("mejor_configuracion", {})
    if cfg.get("k") is None:
        raise ValueError(f"Evidencia de fraccionamiento incompleta: {FRAC_EVIDENCE}")
    evidence = {
        "path": FRAC_EVIDENCE.as_posix(),
        "sha256": sha256_ruta(FRAC_EVIDENCE),
        "training_data_fingerprint_sha256": expected_fingerprint,
    }
    return int(cfg["k"]), "spark_operational_holdout", evidence


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
    *,
    fav_params_override: dict | None = None,
    frac_k_override: int | None = None,
    inherited_from_champion: str | None = None,
) -> dict:
    config = cargar_config(config_path)
    if config.get("mode") != "training":
        raise ValueError("TRAIN Spark requiere una configuración con mode: training.")
    if (fav_params_override is None) != (frac_k_override is None):
        raise ValueError("Los overrides de reentrenamiento deben cubrir ambos modelos.")
    if fav_params_override is not None and not inherited_from_champion:
        raise ValueError("Un override operacional debe identificar el champion del que hereda parámetros.")

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
    spark.sparkContext.addPyFile(str(SRC_DIR / "core" / "objeto_similarity.py"))
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
            data_fingerprint = fingerprint_spark_dataframe(raw_spark)
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
            data_fingerprint = fingerprint_pandas_dataframe(contracts)
            contracts_rows = int(len(contracts))
            raw_spark = pandas_a_spark(spark, contracts)
            medianas_df = None
            input_engine = "pandas_adapter"

        guardar_json_determinista(preprocessor_json, estado)
        procesado = aplicar_preprocesamiento_congelado(
            raw_spark, estado, medianas_df=medianas_df
        )

        if fav_params_override is None:
            num_trees, max_depth, fav_selection_source, fav_evidence = _parametros_favoritismo(
                data_fingerprint
            )
            frac_k, frac_selection_source, frac_evidence = _parametros_fraccionamiento(
                data_fingerprint
            )
            validation_state = "evaluated_same_corpus"
            validation_evidence = {
                "favoritismo": fav_evidence,
                "fraccionamiento": frac_evidence,
            }
        else:
            num_trees = int(fav_params_override["numTrees"])
            max_depth = int(fav_params_override["maxDepth"])
            frac_k = int(frac_k_override)
            fav_selection_source = "champion_inherited_retraining"
            frac_selection_source = "champion_inherited_retraining"
            validation_state = "pending_candidate_evaluation"
            validation_evidence = {
                "inherited_from_champion": inherited_from_champion,
                "reason": "drift/retraining; candidate requiere evaluación antes de eventual promoción",
            }

        fav_features = construir_features_favoritismo(
            procesado,
            label_col="label_favoritismo",
            monto_col=FAVORITISMO_MONTO_OPERACIONAL,
        )
        fav_model, fav_positives, fav_rows = _entrenar_rf_final(
            fav_features, num_trees, max_depth
        )
        fav_model.write().overwrite().save(str(fav_model_dir))
        fav_importances = {
            feature: float(value)
            for feature, value in zip(FAV_FEATURES, fav_model.featureImportances.toArray())
        }

        frac_features = aplicar_senal_interpretable(
            construir_features_ventana_desde_df(
                procesado, label_col="label_fraccionamiento"
            )
        )
        frac_pred, frac_model, frac_scaler = entrenar_modelos_kmeans(
            frac_features, k=frac_k
        )
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
        "validation_state": validation_state,
        "validation_evidence": validation_evidence,
    }
    candidate_hash = hashlib.sha256(
        json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    manifest = {
        "schema_version": 2,
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
            "validation_state": validation_state,
            "validation_evidence": validation_evidence,
        },
        "models": {
            "favoritismo": {
                "framework": "Apache Spark MLlib",
                "algorithm": "RandomForestClassificationModel",
                "features": FAV_FEATURES,
                "amount_source": FAVORITISMO_MONTO_OPERACIONAL,
                "label": "label_favoritismo",
                "feature_importances": fav_importances,
                "params": {
                    "numTrees": num_trees,
                    "maxDepth": max_depth,
                    "selection_source": fav_selection_source,
                },
            },
            "fraccionamiento": {
                "framework": "Apache Spark MLlib",
                "algorithm": "StandardScalerModel + KMeansModel + distancia al centroide",
                "features": FRAC_FEATURES,
                "amount_source": "monto",
                "label": "label_fraccionamiento",
                "params": {
                    "k": int(frac_model.getK()),
                    "selection_source": frac_selection_source,
                },
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
        description="Entrena candidate Spark MLlib con evaluación operacional alineada; no promueve."
    )
    parser.add_argument("--config", default="config/local-training.yaml")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    args = parser.parse_args()
    entrenar(args.config, args.manifest)


if __name__ == "__main__":
    main()
