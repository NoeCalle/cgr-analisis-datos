"""Construye una fuente única de evidencia para la documentación formal.

Los Productos 1-7 y el reporte técnico no deben copiar métricas a mano. Este
script consolida los datasets generados y los JSON de selección/validación en
`outputs/evidencia_documental.json`, que es la única fuente numérica que deben
leer los generadores de DOCX.

La evidencia distingue explícitamente:
- benchmark sintético del PoC;
- validación de integridad sobre datos públicos OCDS/OECE;
- componentes ejecutados del prototipo;
- dependencias institucionales que NO fueron demostradas.
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
    modalidades = (
        contratos["modalidad"].fillna("SIN_DATO").value_counts(dropna=False).to_dict()
    )
    categorias = {}
    if "categoria_principal" in contratos.columns:
        categorias = (
            contratos["categoria_principal"].fillna("SIN_DATO").value_counts(dropna=False).to_dict()
        )

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
            "positivos_sembrados": int(frac["label_fraccionamiento_real"].astype(int).sum()),
            "features": [
                c for c in frac.columns
                if c not in {
                    "id_proveedor", "id_entidad", "objeto", "label_fraccionamiento_real"
                }
            ],
        },
    }


def main():
    comparacion = leer_json("outputs/comparacion_modelos_favoritismo.json")
    tuning_fav = leer_json("outputs/tuning_favoritismo_resumen.json")
    tuning_frac = leer_json("outputs/tuning_fraccionamiento_resumen.json")
    p0 = leer_json("outputs/validacion_p0_datos_reales.json")
    manifest = leer_json("outputs/run_manifest.json", requerido=False)

    evidencia = {
        "schema_version": 1,
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_sha(),
        "naturaleza": (
            "Prototipo independiente. Las métricas sintéticas evalúan el PoC y no estiman "
            "desempeño productivo. Las salidas sobre datos públicos son señales de priorización "
            "para revisión y no constituyen hallazgos ni determinaciones de irregularidad."
        ),
        "sintetico": resumen_sintetico(),
        "seleccion_favoritismo": comparacion,
        "tuning_favoritismo": tuning_fav,
        "tuning_fraccionamiento": tuning_frac,
        "validacion_datos_publicos": p0,
        "run_manifest": manifest,
        "estado_componentes": {
            "implementado_y_probado": [
                "EDA y feature engineering",
                "Random Forest para priorización de favoritismo",
                "Isolation Forest + regla interpretable para posible fraccionamiento",
                "SHAP para explicabilidad del modelo supervisado",
                "Spark MLlib en modo local del PoC",
                "GraphFrames en escenario sintético",
                "Airflow con Python de proyecto separado",
                "simulación local de capas Bronce/Plata/Oro",
                "Delta Lake local con time travel sujeto a retención",
                "esquema T-SQL y RDL de SSRS como artefactos de despliegue",
                "CI de regresión y smoke del pipeline sintético",
                "autoevaluación que genera candidato sin promoción automática",
            ],
            "dependencia_institucional_no_demostrada": [
                "acceso al Datamart y fuentes internas CGR",
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
            "permitir_conteo_obsoleto_solo_como_antecedente_explicito": True,
            "prohibir_pct_no_competitiva": True,
            "prohibir_umbral_fijo_400k_como_regla_general": True,
            "promocion_modelo_requiere_revision_humana": True,
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(evidencia, f, ensure_ascii=False, indent=2)
    print(f"Evidencia documental generada: {OUT.relative_to(ROOT)}")
    return evidencia


if __name__ == "__main__":
    main()
