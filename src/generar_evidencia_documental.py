"""Construye la fuente única de evidencia para la documentación formal.

Los Productos 1-7 y el reporte técnico no copian métricas a mano. Este script
consolida datasets y JSON de selección/validación en
``outputs/evidencia_documental.json``.

La evidencia distingue explícitamente:
- benchmark sintético y benchmarks de compatibilidad;
- validación CV/holdout de los modelos Spark servidos;
- monitoreo ligado al champion activo;
- análisis sintético de pagos, montos y modalidades;
- validación de integridad sobre datos públicos OCDS/OECE;
- dependencias institucionales que no han sido demostradas.

La documentación vigente consume valores actuales. Los antecedentes de cifras o
contratos sustituidos permanecen en Git/auditorías y no se incorporan como parte
de la descripción funcional del sistema.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "evidencia_documental.json"


def leer_json(relativa: str, requerido: bool = True):
    ruta = ROOT / relativa
    if not ruta.exists():
        if requerido:
            raise FileNotFoundError(f"Falta evidencia requerida: {relativa}")
        return None
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def git_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def resumen_sintetico():
    contratos = pd.read_csv(ROOT / "data" / "contratos_siaf_seace.csv")
    fav = pd.read_csv(ROOT / "lakehouse" / "plata" / "dataset_favoritismo.csv")
    frac = pd.read_csv(ROOT / "lakehouse" / "plata" / "dataset_fraccionamiento.csv")

    monto = pd.to_numeric(contratos["monto"], errors="coerce")
    p99 = float(monto.quantile(0.99))
    modalidades = contratos["modalidad"].fillna("SIN_DATO").value_counts(dropna=False).to_dict()
    categorias = {}
    if "categoria_principal" in contratos.columns:
        categorias = contratos["categoria_principal"].fillna("SIN_DATO").value_counts(dropna=False).to_dict()

    return {
        "contratos": int(len(contratos)),
        "columnas_contratos": int(len(contratos.columns)),
        "valores_nulos_totales": int(contratos.isna().sum().sum()),
        "filas_con_algun_nulo": int(contratos.isna().any(axis=1).sum()),
        "p99_monto_pen": p99,
        "registros_sobre_p99": int((monto > p99).sum()),
        "modalidades": {str(k): int(v) for k, v in modalidades.items()},
        "categorias_principales": {str(k): int(v) for k, v in categorias.items()},
        "favoritismo": {
            "pares_proveedor_entidad": int(len(fav)),
            "positivos_sembrados": int(fav["label_favoritismo_real"].astype(int).sum()),
            "features": [
                c for c in fav.columns
                if c not in {"id_proveedor", "id_entidad", "label_favoritismo_real"}
            ],
        },
        "fraccionamiento": {
            "grupos_proveedor_entidad_objeto": int(len(frac)),
            "grupos_proveedor_entidad_objeto_familia": int(len(frac)),
            "positivos_sembrados": int(frac["label_fraccionamiento_real"].astype(int).sum()),
            "usa_objeto_familia": "objeto_familia" in frac.columns,
            "features": [
                c for c in frac.columns
                if c not in {
                    "id_proveedor", "id_entidad", "objeto", "objeto_familia",
                    "label_fraccionamiento_real",
                }
            ],
        },
    }


def main():
    comparacion = leer_json("outputs/comparacion_modelos_favoritismo.json")
    tuning_fav = leer_json("outputs/tuning_favoritismo_resumen.json")
    tuning_frac = leer_json("outputs/tuning_fraccionamiento_resumen.json")
    tuning_fav_spark = leer_json("outputs/tuning_favoritismo_spark_resumen.json")
    tuning_frac_spark = leer_json("outputs/tuning_fraccionamiento_spark_resumen.json")
    registry = leer_json("outputs/model_registry.json")
    monitor_champion = leer_json("outputs/monitoreo_champion.json")
    pagos_modalidades = leer_json("outputs/analisis_pagos_modalidades.json")
    p0 = leer_json("outputs/validacion_p0_datos_reales.json")
    manifest = leer_json("outputs/run_manifest.json", requerido=False)

    spark_profile = registry["serving_profiles"]["spark_mllib"]
    if registry.get("active_serving_profile") != "spark_mllib":
        raise ValueError("La evidencia formal exige spark_mllib como perfil activo del PoC.")
    if monitor_champion.get("champion_id") != spark_profile.get("champion_id"):
        raise ValueError("Monitoreo y registry no apuntan al mismo champion Spark.")

    evidencia = {
        "schema_version": 3,
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_sha(),
        "naturaleza": (
            "Prototipo independiente. Las métricas sintéticas evalúan el PoC y no estiman "
            "desempeño productivo. El análisis de pagos usa datos sintéticos y no representa SIAF real. "
            "Las salidas sobre datos públicos son señales de priorización para revisión y no constituyen "
            "hallazgos ni determinaciones de irregularidad."
        ),
        "sintetico": resumen_sintetico(),
        "analisis_pagos_modalidades": pagos_modalidades,
        "seleccion_favoritismo": comparacion,
        "tuning_favoritismo": tuning_fav,
        "tuning_fraccionamiento": tuning_frac,
        "evaluacion_champion_spark": {
            "champion_id": spark_profile["champion_id"],
            "favoritismo": tuning_fav_spark,
            "fraccionamiento": tuning_frac_spark,
            "registry_models": spark_profile["models"],
        },
        "monitoreo_champion": monitor_champion,
        "validacion_datos_publicos": p0,
        "run_manifest": manifest,
        "estado_componentes": {
            "implementado_y_probado": [
                "EDA y feature engineering",
                "análisis sintético de pagos, montos contractuales y modalidades",
                "Random Forest Spark de favoritismo con CV/holdout del mismo pipeline operacional",
                "KMeans Spark de fraccionamiento con tuning/holdout propios",
                "Isolation Forest como benchmark de compatibilidad para fraccionamiento",
                "Feature Importance ligada al champion Spark activo y SHAP complementario sklearn",
                "objeto_familia y ventanas de 15 días con semántica pandas/Spark alineada",
                "Spark MLlib en modo local/configurable del PoC",
                "GraphFrames en escenario sintético",
                "Airflow con Python de proyecto separado",
                "simulación local de capas Bronce/Plata/Oro",
                "Delta Lake local con time travel sujeto a retención",
                "esquema T-SQL y RDL de SSRS como artefactos de despliegue",
                "CI de regresión y smoke del pipeline sintético",
                "autoevaluación registry-aware del champion activo que genera candidate sin promoción automática",
                "TRAIN/INFERENCE con favoritismo operacional basado en monto_capped congelado",
            ],
            "dependencia_institucional_no_demostrada": [
                "acceso al Datamart y fuentes internas CGR, incluidos pagos SIAF reales",
                "despliegue real DEV/QA/PROD institucional",
                "Git y CI/CD institucionales",
                "SQL Server/SSRS/SSAS/Power BI institucionales ejecutados",
                "HDFS/YARN distribuido sobre infraestructura CGR",
                "certificación funcional con auditores y especialistas de negocio",
                "marcha blanca, transferencia formal y aprobación institucional",
                "ground truth real etiquetado para medir precisión/recall productivos",
            ],
        },
        "criterios_documentales": {
            "usar_termino_senal": True,
            "prohibir_afirmacion_desempeno_productivo": True,
            "permitir_conteo_obsoleto_solo_como_antecedente_explicito": False,
            "prohibir_conteos_obsoletos_en_documentacion_vigente": True,
            "prohibir_narrativa_interna_sprint_etapa_en_entregables": True,
            "prohibir_pct_no_competitiva": True,
            "prohibir_umbral_fijo_400k_como_regla_general": True,
            "promocion_modelo_requiere_revision_humana": True,
            "pagos_sinteticos_no_equivalen_siaf_real": True,
            "modalidad_requiere_contexto_juridico": True,
            "metricas_champion_deben_corresponder_al_pipeline_servido": True,
            "benchmarks_compatibilidad_no_sustituyen_metricas_champion": True,
            "monitoreo_debe_apuntar_al_champion_activo": True,
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(evidencia, f, ensure_ascii=False, indent=2)
    print(f"Evidencia documental generada: {OUT.relative_to(ROOT)}")
    return evidencia


if __name__ == "__main__":
    main()
