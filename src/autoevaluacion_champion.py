"""Autoevaluación del champion ACTIVO y generación de candidates sin promoción.

Lee el registry, exige ``spark_mllib`` activo y evalúa los mismos artefactos que
sirve INFERENCE. El baseline debe coincidir con el fingerprint de entrenamiento
del champion. Se vigilan favoritismo y fraccionamiento. Un trigger puede generar
un candidate usando labels disponibles, pero ese candidate hereda parámetros del
champion y queda explícitamente pendiente de evaluación antes de promoverse.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from pyspark.ml.classification import RandomForestClassificationModel
from pyspark.ml.clustering import KMeansModel
from pyspark.ml.feature import StandardScalerModel
from pyspark.sql import functions as F

from autoevaluacion import calcular_psi
from core.config import cargar_config
from core.fingerprints import fingerprint_pandas_dataframe
from ingestar_canonico import integrar
from registro_modelos import SPARK_PROFILE, cargar_registry_champion
from spark.entrenar_candidato_spark import entrenar as entrenar_candidate_spark
from spark.modelo_favoritismo_spark import (
    construir_features_favoritismo,
    crear_sesion,
    vectorizar,
)
from spark.modelo_fraccionamiento_spark import (
    FEATURES as FRAC_FEATURES,
    construir_features_ventana_desde_df,
    puntuar_con_modelos,
)
from spark.preprocesamiento_serving_spark import (
    aplicar_preprocesamiento_congelado,
    pandas_a_spark,
)

UMBRAL_PSI = 0.25
UMBRAL_RECALL_MINIMO = 0.80
FEATURES_PSI_FAV = [
    "monto_total",
    "pct_contratacion_directa",
    "pct_comparacion_precios",
    "concentracion_objeto",
]
DEFAULT_OUTPUT = Path("outputs/monitoreo_champion.json")
DEFAULT_LOG = Path("outputs/log_reentrenamiento_champion.csv")
DEFAULT_BATCHES = {
    "normal": Path("data/lote_nuevo_normal.csv"),
    "con_drift": Path("data/lote_nuevo_con_drift.csv"),
}


def _procesar(spark, raw: pd.DataFrame, estado: dict):
    return aplicar_preprocesamiento_congelado(
        pandas_a_spark(spark, raw), estado, medianas_df=None
    )


def _recall_at_k(pdf: pd.DataFrame, *, label_col: str = "label", score_col: str = "score") -> float | None:
    if label_col not in pdf.columns:
        return None
    y = pdf[label_col].astype(int).to_numpy()
    n_pos = int(y.sum())
    if not n_pos:
        return None
    idx = np.argsort(-pdf[score_col].to_numpy())[:n_pos]
    return float(y[idx].sum() / n_pos)


def _evaluar_favoritismo(model, baseline_proc, new_proc, *, has_label: bool) -> dict:
    baseline_feat = construir_features_favoritismo(
        baseline_proc,
        label_col="label_favoritismo",
        monto_col="monto_capped",
    )
    new_feat = construir_features_favoritismo(
        new_proc,
        label_col="label_favoritismo" if has_label else None,
        monto_col="monto_capped",
    )
    pred = model.transform(vectorizar(new_feat))
    prob_udf = F.udf(lambda v: float(v[1]), "double")
    select_cols = [*FEATURES_PSI_FAV]
    if has_label:
        select_cols.append("label")
    scored = pred.select(
        *select_cols,
        prob_udf("probability").alias("score"),
    ).toPandas()
    baseline = baseline_feat.select(*FEATURES_PSI_FAV).toPandas()
    psi = {
        feature: float(calcular_psi(baseline[feature].to_numpy(), scored[feature].to_numpy()))
        for feature in FEATURES_PSI_FAV
    }
    psi_max = max(psi.values())
    recall = _recall_at_k(scored)
    return {
        "psi": psi,
        "psi_max": float(psi_max),
        "recall_at_k_champion": recall,
        "trigger_drift": bool(psi_max > UMBRAL_PSI),
        "trigger_recall": bool(recall is not None and recall < UMBRAL_RECALL_MINIMO),
        "scored_groups": int(len(scored)),
        "positivos": int(scored["label"].astype(int).sum()) if has_label else None,
    }


def _evaluar_fraccionamiento(model, scaler, baseline_proc, new_proc, *, has_label: bool) -> dict:
    baseline_feat = construir_features_ventana_desde_df(
        baseline_proc, label_col="label_fraccionamiento"
    )
    new_feat = construir_features_ventana_desde_df(
        new_proc, label_col="label_fraccionamiento" if has_label else None
    )
    baseline_scored = puntuar_con_modelos(baseline_feat, model, scaler)
    new_scored = puntuar_con_modelos(new_feat, model, scaler)

    baseline_pdf = baseline_scored.select(*FRAC_FEATURES, "score_anomalia").toPandas()
    select_cols = [*FRAC_FEATURES, "score_anomalia"]
    if has_label:
        select_cols.append("label")
    new_pdf = new_scored.select(*select_cols).toPandas()

    psi = {
        feature: float(
            calcular_psi(baseline_pdf[feature].to_numpy(), new_pdf[feature].to_numpy())
        )
        for feature in FRAC_FEATURES
    }
    psi_score = float(
        calcular_psi(
            baseline_pdf["score_anomalia"].to_numpy(),
            new_pdf["score_anomalia"].to_numpy(),
        )
    )
    psi_max = max([*psi.values(), psi_score])
    recall = _recall_at_k(new_pdf, score_col="score_anomalia")
    return {
        "psi_features": psi,
        "psi_score_anomalia": psi_score,
        "psi_max": float(psi_max),
        "recall_at_k_champion": recall,
        "trigger_drift": bool(psi_max > UMBRAL_PSI),
        "trigger_recall": bool(recall is not None and recall < UMBRAL_RECALL_MINIMO),
        "scored_groups": int(len(new_pdf)),
        "positivos": int(new_pdf["label"].astype(int).sum()) if has_label else None,
    }


def _evaluar_lote(spark, fav_model, frac_model, frac_scaler, estado, train_raw, raw_new, escenario):
    baseline_proc = _procesar(spark, train_raw, estado).cache()
    new_proc = _procesar(spark, raw_new, estado).cache()
    has_fav_label = "label_favoritismo" in raw_new.columns
    has_frac_label = "label_fraccionamiento" in raw_new.columns
    try:
        fav = _evaluar_favoritismo(
            fav_model, baseline_proc, new_proc, has_label=has_fav_label
        )
        frac = _evaluar_fraccionamiento(
            frac_model, frac_scaler, baseline_proc, new_proc, has_label=has_frac_label
        )
    finally:
        baseline_proc.unpersist()
        new_proc.unpersist()

    trigger_drift = fav["trigger_drift"] or frac["trigger_drift"]
    trigger_recall = fav["trigger_recall"] or frac["trigger_recall"]
    return {
        "escenario": escenario,
        # Campos legacy conservados para consumidores existentes: representan
        # favoritismo; el detalle de ambos modelos queda debajo.
        "psi": fav["psi"],
        "psi_max": float(max(fav["psi_max"], frac["psi_max"])),
        "recall_at_k_champion": fav["recall_at_k_champion"],
        "trigger_drift": bool(trigger_drift),
        "trigger_recall": bool(trigger_recall),
        "retraining_required": bool(trigger_drift or trigger_recall),
        "scored_groups": fav["scored_groups"],
        "positivos": fav["positivos"],
        "labels_available_for_retraining": bool(has_fav_label and has_frac_label),
        "favoritismo": fav,
        "fraccionamiento": frac,
    }


def _crear_config_retraining(base_config: dict, contracts_path: Path, target: Path):
    cfg = json.loads(json.dumps(base_config))
    cfg["source"]["type"] = "local_csv"
    cfg["source"].pop("tables", None)
    cfg["source"]["datasets"] = {"contracts": contracts_path.as_posix()}
    cfg["mapping"]["contracts"] = {
        "id_contrato": "id_contrato",
        "id_proveedor": "id_proveedor",
        "id_entidad": "id_entidad",
        "id_funcionario": "id_funcionario",
        "monto": "monto",
        "fecha_contrato": "fecha_contrato",
        "modalidad": "modalidad",
        "objeto": "objeto",
        "categoria_principal": "categoria_principal",
        "label_favoritismo": "label_favoritismo",
        "label_fraccionamiento": "label_fraccionamiento",
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")


def ejecutar(
    registry_path: str | Path = "outputs/model_registry.json",
    config_path: str | Path = "config/local-training.yaml",
    output_path: str | Path = DEFAULT_OUTPUT,
    log_path: str | Path = DEFAULT_LOG,
    *,
    batch_paths: dict[str, str | Path] | None = None,
):
    registry = cargar_registry_champion(registry_path, profile=SPARK_PROFILE)
    if registry["active_serving_profile"] != SPARK_PROFILE:
        raise ValueError("La autoevaluación debe ejecutar el mismo perfil que serving activo.")

    config = cargar_config(config_path)
    if config["source"]["type"] == "spark_sql":
        raise ValueError(
            "El monitor batch pandas del PoC no colecta spark_sql. En CGR debe configurarse "
            "un monitor distribuido sobre la plataforma Spark institucional."
        )
    datasets, _ = integrar(config)
    train_raw = datasets["contracts"]
    expected_fingerprint = registry["training"].get("training_data_fingerprint_sha256")
    baseline_fingerprint = fingerprint_pandas_dataframe(train_raw)
    if not expected_fingerprint or baseline_fingerprint != expected_fingerprint:
        raise ValueError(
            "Baseline de monitor no corresponde al corpus del champion: "
            f"registry={expected_fingerprint!r} baseline={baseline_fingerprint!r}"
        )

    estado = json.loads(
        Path(registry["artifacts"]["preprocessor_json"]["path"]).read_text(encoding="utf-8")
    )
    batches = batch_paths or DEFAULT_BATCHES

    spark = crear_sesion("cgr-monitoreo-champion-activo", operational=True)
    spark.sparkContext.setLogLevel("ERROR")
    spark.sparkContext.addPyFile(str(Path(__file__).resolve().parent / "core" / "objeto_similarity.py"))
    spark.sparkContext.addPyFile(str(Path(__file__).resolve().parent / "umbrales_normativos.py"))
    try:
        fav_model = RandomForestClassificationModel.load(
            registry["artifacts"]["favoritismo_model"]["path"]
        )
        frac_model = KMeansModel.load(registry["artifacts"]["fraccionamiento_model"]["path"])
        frac_scaler = StandardScalerModel.load(
            registry["artifacts"]["fraccionamiento_scaler"]["path"]
        )
        resultados = []
        lotes = {}
        for escenario, batch_path in batches.items():
            path = Path(batch_path)
            if not path.exists():
                raise FileNotFoundError(f"Lote de monitoreo no encontrado ({escenario}): {path}")
            raw = pd.read_csv(path, parse_dates=["fecha_contrato"])
            raw = raw.rename(columns={
                "es_favoritismo_real": "label_favoritismo",
                "es_fraccionamiento_real": "label_fraccionamiento",
            })
            lotes[escenario] = raw
            resultados.append(
                _evaluar_lote(
                    spark, fav_model, frac_model, frac_scaler,
                    estado, train_raw, raw, escenario,
                )
            )
    finally:
        spark.stop()

    fav_params = registry["models"]["favoritismo"]["params"]
    frac_params = registry["models"]["fraccionamiento"]["params"]
    base_config = config
    for resultado in resultados:
        resultado["active_profile"] = SPARK_PROFILE
        resultado["champion_id"] = registry["champion_id"]
        resultado["candidate_generated"] = False
        resultado["candidate_id"] = None
        resultado["automatic_promotion"] = False
        if not resultado["retraining_required"]:
            continue
        if not resultado["labels_available_for_retraining"]:
            resultado["candidate_blocked_reason"] = (
                "drift detectado pero el lote no contiene ambos labels aprobados; "
                "no se genera candidate automáticamente"
            )
            continue

        escenario = resultado["escenario"]
        runtime = Path("outputs/runtime/retraining") / escenario
        input_dir = runtime / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        combined = pd.concat([train_raw, lotes[escenario]], ignore_index=True)
        contracts_path = input_dir / "contracts_training.csv"
        combined.to_csv(contracts_path, index=False)
        cfg_path = input_dir / "training.yaml"
        _crear_config_retraining(base_config, contracts_path, cfg_path)

        manifest_path = runtime / "candidate" / "candidate_manifest.json"
        manifest = entrenar_candidate_spark(
            cfg_path,
            manifest_path,
            fav_params_override={
                "numTrees": int(fav_params["numTrees"]),
                "maxDepth": int(fav_params["maxDepth"]),
            },
            frac_k_override=int(frac_params["k"]),
            inherited_from_champion=registry["champion_id"],
        )
        resultado["candidate_generated"] = True
        resultado["candidate_id"] = manifest["candidate_id"]
        resultado["candidate_manifest"] = manifest_path.as_posix()
        resultado["candidate_validation_state"] = manifest["training"]["validation_state"]

    payload = {
        "schema_version": 2,
        "active_profile": SPARK_PROFILE,
        "champion_id": registry["champion_id"],
        "champion_framework": registry["models"]["favoritismo"]["framework"],
        "baseline_training_data_fingerprint_sha256": baseline_fingerprint,
        "baseline_matches_champion": True,
        "feature_source": "champion preprocessor + ambos modelos Spark activos",
        "gates": {"psi_max": UMBRAL_PSI, "recall_at_k_min": UMBRAL_RECALL_MINIMO},
        "scenarios": resultados,
        "automatic_promotion": False,
        "notice": (
            "Los candidates por drift heredan parámetros del champion y quedan pendientes "
            "de evaluación/promoción explícita; no existe autopromoción."
        ),
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    log_rows = []
    for r in resultados:
        log_rows.append({
            "escenario": r["escenario"],
            "active_profile": SPARK_PROFILE,
            "champion_id": registry["champion_id"],
            "baseline_matches_champion": True,
            "psi_monto_total": r["favoritismo"]["psi"]["monto_total"],
            "psi_pct_contratacion_directa": r["favoritismo"]["psi"]["pct_contratacion_directa"],
            "psi_pct_comparacion_precios": r["favoritismo"]["psi"]["pct_comparacion_precios"],
            "psi_concentracion_objeto": r["favoritismo"]["psi"]["concentracion_objeto"],
            "psi_favoritismo_max": r["favoritismo"]["psi_max"],
            "psi_fraccionamiento_max": r["fraccionamiento"]["psi_max"],
            "psi_max": r["psi_max"],
            "recall_at_k_champion": r["favoritismo"]["recall_at_k_champion"],
            "recall_at_k_fraccionamiento": r["fraccionamiento"]["recall_at_k_champion"],
            "retraining_required": r["retraining_required"],
            "candidate_generated": r["candidate_generated"],
            "candidate_id": r["candidate_id"],
            "automatic_promotion": False,
        })
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(log_rows).to_csv(log_path, index=False)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def _parse_batches(values: list[str] | None) -> dict[str, Path] | None:
    if not values:
        return None
    out: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--batch debe usar formato NOMBRE=RUTA")
        name, raw_path = value.split("=", 1)
        name = name.strip()
        raw_path = raw_path.strip()
        if not name or not raw_path:
            raise ValueError("--batch debe usar formato NOMBRE=RUTA no vacío")
        out[name] = Path(raw_path)
    return out


def main():
    parser = argparse.ArgumentParser(description="Autoevalúa el champion Spark activo del registry.")
    parser.add_argument("--registry", default="outputs/model_registry.json")
    parser.add_argument("--config", default="config/local-training.yaml")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument(
        "--batch",
        action="append",
        help=(
            "Lote a monitorizar en formato NOMBRE=RUTA. Puede repetirse. "
            "Si se omite, usa los dos lotes sintéticos de regresión del PoC."
        ),
    )
    args = parser.parse_args()
    ejecutar(
        args.registry,
        args.config,
        args.output,
        args.log,
        batch_paths=_parse_batches(args.batch),
    )


if __name__ == "__main__":
    main()
