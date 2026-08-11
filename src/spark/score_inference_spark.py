"""INFERENCE operacional con Apache Spark MLlib.

Para ``source.type=spark_sql`` conserva un DataFrame Spark desde la tabla/vista
hasta el scoring y escribe rankings distribuidos en Parquet. CSV/SQL Server
mantienen un adaptador pandas->Spark y CSV único por compatibilidad local.

No contiene fit, tuning ni requiere labels. Los artefactos champion se verifican
por SHA-256 al cargar y nuevamente antes de publicar. Las salidas se escriben en
staging y solo se hacen visibles en el directorio final después del gate.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

from pyspark.ml.classification import RandomForestClassificationModel
from pyspark.ml.clustering import KMeansModel
from pyspark.ml.feature import StandardScalerModel
from pyspark.sql import functions as F

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

from core.config import cargar_config
from ingestar_canonico import integrar, integrar_spark
from registro_modelos import (
    SPARK_PROFILE,
    cargar_registry_champion,
    guardar_json_determinista,
    sha256_ruta,
)
from spark.modelo_favoritismo_spark import (
    construir_features_favoritismo,
    crear_sesion,
    generar_ranking,
    vectorizar,
)
from spark.modelo_fraccionamiento_spark import (
    aplicar_senal_interpretable,
    construir_features_ventana_desde_df,
    puntuar_con_modelos,
)
from spark.preprocesamiento_serving_spark import (
    aplicar_preprocesamiento_congelado,
    pandas_a_spark,
)

DEFAULT_OUTPUT_DIR = Path("outputs/runtime/inference_spark/latest")
FAVORITISMO_MONTO_OPERACIONAL = "monto_capped"


def _write_single_csv_spark(df, target: Path) -> None:
    """CSV único para compatibilidad local; no convierte el ranking a pandas."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".{target.name}.spark-tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    df.coalesce(1).write.mode("overwrite").option("header", True).csv(str(tmp))
    parts = sorted(tmp.glob("part-*.csv"))
    if len(parts) != 1:
        raise RuntimeError(f"Spark no produjo un único part CSV para {target}: {len(parts)}")
    shutil.copy2(parts[0], target)
    shutil.rmtree(tmp)


def _write_rankings(ranking_fav, ranking_frac, output_dir: Path, *, spark_native: bool) -> dict:
    output_dir.mkdir(parents=True, exist_ok=False)
    if spark_native:
        fav_name = "ranking_riesgo_favoritismo_spark.parquet"
        frac_name = "ranking_riesgo_fraccionamiento_spark.parquet"
        ranking_fav.write.mode("errorifexists").parquet(str(output_dir / fav_name))
        ranking_frac.write.mode("errorifexists").parquet(str(output_dir / frac_name))
        return {
            "format": "parquet_distributed",
            "favoritismo_name": fav_name,
            "fraccionamiento_name": frac_name,
        }

    fav_name = "ranking_riesgo_favoritismo_spark.csv"
    frac_name = "ranking_riesgo_fraccionamiento_spark.csv"
    _write_single_csv_spark(ranking_fav, output_dir / fav_name)
    _write_single_csv_spark(ranking_frac, output_dir / frac_name)
    return {
        "format": "csv_single_file_compatibility",
        "favoritismo_name": fav_name,
        "fraccionamiento_name": frac_name,
    }


def _integridad_champion(registry: dict) -> dict[str, bool]:
    return {
        nombre: sha256_ruta(spec["path"]) == spec["sha256"]
        for nombre, spec in registry["artifacts"].items()
    }


def _publicar_directorio_staging(staging: Path, final: Path) -> None:
    """Sustituye el directorio final con rollback local si falla el rename."""
    final.parent.mkdir(parents=True, exist_ok=True)
    backup = final.parent / f".{final.name}.backup-{uuid.uuid4().hex}"
    had_previous = final.exists()
    if had_previous:
        os.replace(final, backup)
    try:
        os.replace(staging, final)
    except Exception:
        if had_previous and backup.exists() and not final.exists():
            os.replace(backup, final)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)


def ejecutar_inference_spark(
    config_path: str | Path,
    registry_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    summary_path: str | Path | None = None,
) -> dict:
    config = cargar_config(config_path)
    if config.get("mode") != "inference":
        raise ValueError("INFERENCE Spark requiere una configuración con mode: inference.")

    registry = cargar_registry_champion(registry_path, profile=SPARK_PROFILE)
    if registry["active_serving_profile"] != SPARK_PROFILE:
        raise ValueError(
            "El registry contiene champion Spark pero no está declarado como serving activo."
        )

    preprocessor_path = Path(registry["artifacts"]["preprocessor_json"]["path"])
    estado = json.loads(preprocessor_path.read_text(encoding="utf-8"))

    spark = crear_sesion("cgr-inference-spark-mllib", operational=True)
    spark_mode = spark.sparkContext.master
    spark.sparkContext.setLogLevel("ERROR")
    spark.sparkContext.addPyFile(str(SRC_DIR / "umbrales_normativos.py"))

    source_type = config["source"]["type"]
    spark_native = source_type == "spark_sql"
    staging = None
    try:
        if spark_native:
            datasets, integration_summary = integrar_spark(config, spark=spark)
            raw_spark = datasets["contracts"]
            contracts_rows = int(integration_summary["domains"]["contracts"]["rows"])
            input_engine = "spark_native"
        else:
            datasets, integration_summary = integrar(config)
            contracts = datasets["contracts"]
            contracts_rows = int(len(contracts))
            raw_spark = pandas_a_spark(spark, contracts)
            input_engine = "pandas_adapter"

        labels_present = sorted(
            c for c in raw_spark.columns if c in {"label_favoritismo", "label_fraccionamiento"}
        )
        if labels_present:
            raise ValueError(f"INFERENCE Spark no debe consumir ground truth: {labels_present}")

        medianas_spec = registry["artifacts"].get("preprocessor_medians")
        medianas_df = (
            spark.read.parquet(medianas_spec["path"])
            if medianas_spec is not None
            else None
        )
        if estado.get("monto_mediana_por_objeto_external", False) and medianas_df is None:
            raise ValueError(
                "Champion Spark-native incompleto: falta artefacto preprocessor_medians."
            )

        procesado = aplicar_preprocesamiento_congelado(
            raw_spark, estado, medianas_df=medianas_df
        )

        fav_features = construir_features_favoritismo(
            procesado,
            label_col=None,
            monto_col=FAVORITISMO_MONTO_OPERACIONAL,
        )
        expected_fav = registry["models"]["favoritismo"]["features"]
        faltan_fav = sorted(set(expected_fav) - set(fav_features.columns))
        if faltan_fav:
            raise ValueError(f"Faltan features Spark de favoritismo: {faltan_fav}")

        fav_model = RandomForestClassificationModel.load(
            registry["artifacts"]["favoritismo_model"]["path"]
        )
        fav_pred = fav_model.transform(vectorizar(fav_features))
        ranking_fav = generar_ranking(fav_pred, include_label=False)

        frac_features = aplicar_senal_interpretable(
            construir_features_ventana_desde_df(procesado, label_col=None)
        )
        expected_frac = registry["models"]["fraccionamiento"]["features"]
        faltan_frac = sorted(set(expected_frac) - set(frac_features.columns))
        if faltan_frac:
            raise ValueError(f"Faltan features Spark de fraccionamiento: {faltan_frac}")

        frac_model = KMeansModel.load(registry["artifacts"]["fraccionamiento_model"]["path"])
        frac_scaler = StandardScalerModel.load(
            registry["artifacts"]["fraccionamiento_scaler"]["path"]
        )
        frac_pred = puntuar_con_modelos(frac_features, frac_model, frac_scaler)
        ranking_frac = (
            frac_pred.select(
                "id_proveedor",
                "id_entidad",
                "objeto",
                "max_contratos_ventana_15d",
                "pct_montos_bajo_umbral",
                "score_anomalia",
                "senal_priorizacion_fraccionamiento",
            )
            .orderBy(F.desc("score_anomalia"))
        )

        # Fuerza el scoring antes de cualquier publicación externa.
        fav_rows = int(ranking_fav.count())
        frac_rows = int(ranking_frac.count())
        integrity_pre_publish = _integridad_champion(registry)
        if not all(integrity_pre_publish.values()):
            raise RuntimeError("Un champion Spark cambió durante scoring; no se publica salida.")

        output_dir = Path(output_dir)
        staging = output_dir.parent / f".{output_dir.name}.staging-{uuid.uuid4().hex}"
        if staging.exists():
            shutil.rmtree(staging)
        detail_staging = _write_rankings(
            ranking_fav, ranking_frac, staging, spark_native=spark_native
        )

        # Segundo gate después de materializar la salida en staging. Si falla,
        # el directorio final anterior permanece intacto.
        integrity_after_staging = _integridad_champion(registry)
        if not all(integrity_after_staging.values()):
            raise RuntimeError("Un champion Spark cambió antes de publicar; staging descartado.")

        detail_outputs = {
            "format": detail_staging["format"],
            "favoritismo": (output_dir / detail_staging["favoritismo_name"]).as_posix(),
            "fraccionamiento": (output_dir / detail_staging["fraccionamiento_name"]).as_posix(),
            "publication": "staging_then_atomic_directory_swap",
        }
        summary = {
            "schema_version": 3,
            "mode": "inference",
            "engine": "Apache Spark MLlib",
            "spark_mode": spark_mode,
            "source_type": integration_summary["source_type"],
            "input_engine": input_engine,
            "spark_native_ingestion": spark_native,
            "pandas_materialization": not spark_native,
            "preprocessor_medians_external": bool(medianas_spec),
            "registry_schema_version": registry["registry_schema_version"],
            "serving_profile": registry["profile_name"],
            "active_serving_profile": registry["active_serving_profile"],
            "champion_id": registry["champion_id"],
            "institutional_approval": registry["promotion"]["institutional_approval"],
            "contracts_rows": contracts_rows,
            "favoritismo_scored_rows": fav_rows,
            "fraccionamiento_scored_rows": frac_rows,
            "favoritismo_amount_source": FAVORITISMO_MONTO_OPERACIONAL,
            "fraccionamiento_amount_source": "monto",
            "labels_consumed": False,
            "training_invoked": False,
            "tuning_invoked": False,
            "sklearn_serving_dependency": False,
            "champion_integrity_verified": True,
            "integrity_gate_before_publish": integrity_after_staging,
            "detail_outputs": detail_outputs,
            "notice": (
                "Scores de priorización del PoC; no constituyen hallazgos de control "
                "ni decisión jurídica. Clúster/infraestructura CGR pendientes."
            ),
        }

        # Si el summary pertenece al output, entra en el mismo staging. Si se
        # solicita una ruta externa (CI), se escribe atómicamente después de
        # publicar los rankings ya verificados.
        external_summary = summary_path is not None
        if not external_summary:
            guardar_json_determinista(staging / "inference_summary.json", summary)

        _publicar_directorio_staging(staging, output_dir)
        staging = None
        if external_summary:
            guardar_json_determinista(summary_path, summary)

        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary
    finally:
        if staging is not None and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        spark.stop()


def main():
    parser = argparse.ArgumentParser(description="Puntúa con champion Spark MLlib; no entrena.")
    parser.add_argument("--config", default="config/local.yaml")
    parser.add_argument("--registry", default="outputs/model_registry.json")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--summary", default=None)
    args = parser.parse_args()
    ejecutar_inference_spark(args.config, args.registry, args.output_dir, args.summary)


if __name__ == "__main__":
    main()
