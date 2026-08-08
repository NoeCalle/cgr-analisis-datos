"""Monitor operacional de solo lectura para el PoC CGR 1.8.2.

Consolida el estado del serving, la integridad declarada del champion y la
última evidencia de deriva/reentrenamiento. No entrena modelos, no hace tuning y
no promueve candidates. La operación institucional, alertamiento y aprobación
siguen dependiendo de CGR.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from registro_modelos import guardar_json_determinista

DEFAULT_REGISTRY = Path("outputs/model_registry.json")
DEFAULT_INFERENCE = Path("outputs/inference_spark_smoke_summary.json")
DEFAULT_LOG = Path("outputs/log_reentrenamiento.csv")
DEFAULT_OUTPUT = Path("outputs/monitoreo_modelos_resumen.json")


def _leer_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _ultima_decision(log_path: Path) -> dict | None:
    if not log_path.exists():
        return None
    df = pd.read_csv(log_path)
    if df.empty:
        return None
    row = df.iloc[-1].to_dict()
    limpio = {}
    for key, value in row.items():
        if pd.isna(value):
            limpio[key] = None
        elif hasattr(value, "item"):
            limpio[key] = value.item()
        else:
            limpio[key] = value
    return limpio


def construir_resumen(
    registry_path: str | Path = DEFAULT_REGISTRY,
    inference_path: str | Path = DEFAULT_INFERENCE,
    log_path: str | Path = DEFAULT_LOG,
) -> dict:
    registry_path = Path(registry_path)
    inference_path = Path(inference_path)
    log_path = Path(log_path)

    registry = _leer_json(registry_path)
    inference = _leer_json(inference_path)
    ultima = _ultima_decision(log_path)

    active_profile = registry.get("active_serving_profile") if registry else None
    active = None
    if registry and active_profile:
        active = registry.get("serving_profiles", {}).get(active_profile)

    alertas: list[str] = []
    if registry is None:
        alertas.append("registry_no_disponible")
    if active_profile != "spark_mllib":
        alertas.append("serving_activo_no_es_spark_mllib")
    if active and active.get("promotion", {}).get("institutional_approval") is not False:
        alertas.append("flag_aprobacion_institucional_inesperado")
    if inference is None:
        alertas.append("smoke_inference_no_disponible")
    else:
        if inference.get("champion_integrity_verified") is not True:
            alertas.append("integridad_champion_no_verificada")
        if inference.get("labels_consumed") is not False:
            alertas.append("inference_consumio_labels")
        if inference.get("training_invoked") is not False:
            alertas.append("inference_invoco_training")
        if inference.get("tuning_invoked") is not False:
            alertas.append("inference_invoco_tuning")
        if inference.get("sklearn_serving_dependency") is not False:
            alertas.append("dependencia_sklearn_en_serving")
        if inference.get("favoritismo_amount_source") != "monto_capped":
            alertas.append("favoritismo_no_usa_monto_capped")

    # El log histórico de autoevaluación es evidencia metodológica del PoC. Su
    # candidate no se considera aprobación ni se activa automáticamente.
    if ultima and bool(ultima.get("promocion_automatica")):
        alertas.append("promocion_automatica_detectada")

    return {
        "schema_version": 1,
        "mode": "monitoring_read_only",
        "nature": "PoC independiente; no constituye monitoreo productivo CGR",
        "active_serving_profile": active_profile,
        "champion_id": active.get("champion_id") if active else None,
        "institutional_approval": (
            active.get("promotion", {}).get("institutional_approval") if active else None
        ),
        "last_inference": {
            "engine": inference.get("engine") if inference else None,
            "contracts_rows": inference.get("contracts_rows") if inference else None,
            "favoritismo_scored_rows": inference.get("favoritismo_scored_rows") if inference else None,
            "fraccionamiento_scored_rows": inference.get("fraccionamiento_scored_rows") if inference else None,
            "champion_integrity_verified": (
                inference.get("champion_integrity_verified") if inference else None
            ),
            "favoritismo_amount_source": (
                inference.get("favoritismo_amount_source") if inference else None
            ),
        },
        "last_drift_retraining_decision": ultima,
        "automatic_promotion_allowed": False,
        "training_invoked": False,
        "tuning_invoked": False,
        "alerts": alertas,
        "healthy_poc_contract": len(alertas) == 0,
        "institutional_dependency": (
            "Alertamiento, telemetría, SLAs, observabilidad, permisos y aprobación de modelos "
            "en DEV/QA/PROD deben integrarse con las plataformas y responsables que defina CGR."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="Consolida monitoreo de solo lectura del PoC.")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--inference", default=str(DEFAULT_INFERENCE))
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    resumen = construir_resumen(args.registry, args.inference, args.log)
    guardar_json_determinista(args.output, resumen)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    if not resumen["healthy_poc_contract"]:
        raise SystemExit("Monitor PoC detectó alertas de contrato: " + ", ".join(resumen["alerts"]))


if __name__ == "__main__":
    main()
