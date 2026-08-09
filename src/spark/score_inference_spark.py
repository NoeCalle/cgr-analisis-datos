"""INFERENCE operacional con Apache Spark MLlib.

Contrato:
  fuente mode=inference -> mapping canónico -> preprocesamiento congelado JSON
  -> feature engineering Spark -> modelos champion MLlib -> rankings runtime

No contiene fit, tuning ni requiere labels. Los artefactos champion se verifican
por SHA-256 antes y después del scoring. Sprint 4 usa ``monto_capped`` en
favoritismo, idéntico al TRAIN operacional promovido.

El master de Spark se obtiene de la sesión operacional creada por
``crear_sesion`` y puede configurarse con ``CGR_SPARK_MASTER``. El default local
se conserva únicamente para poder ejecutar el PoC fuera de infraestructura CGR.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pyspark.ml.classification import RandomForestClassificationModel
from pyspark.ml.clustering import KMeansModel
from pyspark.ml.feature import StandardScalerModel
from pyspark.sql import functions as F

SRC_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_DIR))

from core.config import cargar_config
from ingestar_canonico import integrar
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


def ejecutar_inference_spark(
    config_path: str | Path,
    registry_path: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    summary_path: str | Path | None = None,
) -> dict:
    config = cargar_config(config_path)
    if config.get("mode") != "inference":
        raise ValueError("INFERENCE Spark requiere una configuración con mode: inference.")

    datasets, integration_summary = integrar(config)
    contracts = datasets["contracts"]
    labels_present = sorted(
        c for c in contracts.columns if c in {"label_favoritismo", "label_fraccionamiento"}
    )
    if labels_present:
        raise ValueError(f"INFERENCE Spark no debe consumir ground truth: {labels_present}")

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
    try:
        raw_spark = pandas_a_spark(spark, contracts)
        procesado = aplicar_preprocesamiento_congelado(raw_spark, estado)

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
        ranking_fav = generar_ranking(fav_pred, include_label=False).toPandas()

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
            .toPandas()
        )

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        fav_path = output_dir / "ranking_riesgo_favoritismo_spark.csv"
        frac_path = output_dir / "ranking_riesgo_fraccionamiento_spark.csv"
        ranking_fav.to_csv(fav_path, index=False)
        ranking_frac.to_csv(frac_path, index=False)

        integrity_after = {
            nombre: sha256_ruta(spec["path"]) == spec["sha256"]
            for nombre, spec in registry["artifacts"].items()
        }
        if not all(integrity_after.values()):
            raise RuntimeError("Un champion Spark cambió durante inference.")

        summary = {
            "schema_version": 1,
            "mode": "inference",
            "engine": "Apache Spark MLlib",
            "spark_mode": spark_mode,
            "source_type": integration_summary["source_type"],
            "registry_schema_version": registry["registry_schema_version"],
            "serving_profile": registry["profile_name"],
            "active_serving_profile": registry["active_serving_profile"],
            "champion_id": registry["champion_id"],
            "institutional_approval": registry["promotion"]["institutional_approval"],
            "contracts_rows": int(len(contracts)),
            "favoritismo_scored_rows": int(len(ranking_fav)),
            "fraccionamiento_scored_rows": int(len(ranking_frac)),
            "favoritismo_amount_source": FAVORITISMO_MONTO_OPERACIONAL,
            "fraccionamiento_amount_source": "monto",
            "labels_consumed": False,
            "training_invoked": False,
            "tuning_invoked": False,
            "sklearn_serving_dependency": False,
            "champion_integrity_verified": bool(all(integrity_after.values())),
            "detail_outputs": {
                "favoritismo": fav_path.as_posix(),
                "fraccionamiento": frac_path.as_posix(),
            },
            "notice": (
                "Scores de priorización del PoC; no constituyen hallazgos de control "
                "ni decisión jurídica. Clúster/infraestructura CGR pendientes."
            ),
        }
        if summary_path is None:
            summary_path = output_dir / "inference_summary.json"
        guardar_json_determinista(summary_path, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary
    finally:
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
