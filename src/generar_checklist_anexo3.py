"""Genera el checklist reproducible del Anexo 3 del TDR público.

Estados:
- ✅ cubierto por evidencia verificable del PoC.
- 🟡 cubierto parcialmente; el PoC aporta evidencia, pero el criterio literal
  requiere información/validación institucional no disponible públicamente.
- 🔵 dependencia institucional CGR: no es cerrable desde este repositorio.
- 🔴 brecha técnica del PoC que sí debería poder cerrarse aquí.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from dependencias_cgr import POR_ID, validar_catalogo

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "outputs" / "checklist_anexo3.json"
OUT_MD = ROOT / "docs" / "Checklist_Anexo_03.md"


def ok(*rutas: str) -> bool:
    return all((ROOT / ruta).exists() for ruta in rutas)


def deps(*ids: str) -> list[str]:
    for dep_id in ids:
        if dep_id not in POR_ID:
            raise ValueError(f"Dependencia CGR desconocida: {dep_id}")
    return list(ids)


def item(numero, criterio, categoria, estado, evidencia, residual, dependencias=None, verificacion=True):
    dependencias = dependencias or []
    if estado in {"✅", "🟡"} and not verificacion:
        estado = "🔴"
        residual = "Falta evidencia local esperada; revisar pipeline/CI antes de considerar el criterio cubierto."
    if estado in {"🟡", "🔵"} and not dependencias:
        raise ValueError(f"Criterio {numero} {estado} sin dependencia CGR canónica")
    return {
        "numero": numero,
        "criterio": criterio,
        "categoria": categoria,
        "estado": estado,
        "evidencia_repo": evidencia,
        "dependencias_cgr": dependencias,
        "residual": residual,
    }


def construir():
    validar_catalogo()
    items = [
        item(
            1,
            "Exploración del análisis de datos",
            "Documentación",
            "✅",
            ["src/eda.py", "outputs/charts/01_distribucion_montos.png", "outputs/charts/04_serie_temporal.png"],
            "Sin residual técnico relevante para el PoC; la EDA se repetirá sobre datos internos al desplegar institucionalmente.",
            verificacion=ok("src/eda.py", "outputs/charts/01_distribucion_montos.png", "outputs/charts/04_serie_temporal.png"),
        ),
        item(
            2,
            "Calidad e ingeniería de características: uso exclusivo de capas Plata/Oro del Datamart institucional y justificación estadística de nulos/outliers",
            "Preparación de Datos",
            "🟡",
            ["lakehouse/plata/dataset_favoritismo.csv", "lakehouse/plata/dataset_fraccionamiento.csv", "src/preprocesamiento.py", "reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx"],
            "El PoC usa Plata/Oro locales y documenta nulos/outliers; el requisito literal del Datamart institucional requiere CGR-DEP-01 y CGR-DEP-06.",
            deps("CGR-DEP-01", "CGR-DEP-06"),
            ok("lakehouse/plata/dataset_favoritismo.csv", "lakehouse/plata/dataset_fraccionamiento.csv", "src/preprocesamiento.py"),
        ),
        item(
            3,
            "Estándares institucionales de extracción SQL: LEFT JOIN, lógica de cortocircuito y prohibición de Full Table Scans en tablas de hechos",
            "Estándares de Código",
            "🟡",
            ["src/spark/estandares_sql.py", "outputs/extraccion_estandar_sql.csv"],
            "Las técnicas están demostradas localmente; la conformidad literal requiere CGR-DEP-01, CGR-DEP-02 y CGR-DEP-06.",
            deps("CGR-DEP-01", "CGR-DEP-02", "CGR-DEP-06"),
            ok("src/spark/estandares_sql.py", "outputs/extraccion_estandar_sql.csv"),
        ),
        item(
            4,
            "Performance y validación del modelo: superar umbrales mínimos de Accuracy, F1-Score y AUC-ROC",
            "Analítica Avanzada",
            "🟡",
            [
                "outputs/tuning_favoritismo_spark_resumen.json",
                "outputs/tuning_fraccionamiento_spark_resumen.json",
                "outputs/tuning_favoritismo_resumen.json",
                "outputs/tuning_fraccionamiento_resumen.json",
            ],
            "El PoC reporta holdouts del pipeline operacional Spark y benchmarks de compatibilidad; el TDR público exige umbrales mínimos sin publicar sus valores. La conformidad productiva requiere CGR-DEP-03 y CGR-DEP-06.",
            deps("CGR-DEP-03", "CGR-DEP-06"),
            ok(
                "outputs/tuning_favoritismo_spark_resumen.json",
                "outputs/tuning_fraccionamiento_spark_resumen.json",
                "outputs/tuning_favoritismo_resumen.json",
                "outputs/tuning_fraccionamiento_resumen.json",
            ),
        ),
        item(
            5,
            "Interpretabilidad orientada a auditoría (SHAP, LIME o Feature Importance)",
            "Valor de Negocio",
            "✅",
            [
                "outputs/model_registry.json",
                "outputs/tuning_favoritismo_spark_resumen.json",
                "outputs/charts/07_shap_summary_favoritismo.png",
                "outputs/charts/08_shap_waterfall_caso.png",
            ],
            "El champion Spark activo registra Feature Importance por variable en el registry; SHAP se conserva como evidencia complementaria del benchmark sklearn. La interpretación institucional final requiere casos CGR.",
            verificacion=ok(
                "outputs/model_registry.json",
                "outputs/tuning_favoritismo_spark_resumen.json",
                "outputs/charts/07_shap_summary_favoritismo.png",
                "outputs/charts/08_shap_waterfall_caso.png",
            ),
        ),
        item(
            6,
            "Despliegue, autenticación y MLOps: código versionado en Git institucional",
            "Infraestructura",
            "🔵",
            [".github/workflows/tests.yml", "airflow_home/dags/dag_modulo_analisis_datos.py", "outputs/run_manifest.json"],
            "El PoC demuestra CI/MLOps local; el cierre literal requiere CGR-DEP-04 y CGR-DEP-06.",
            deps("CGR-DEP-04", "CGR-DEP-06"),
            True,
        ),
        item(
            7,
            "Integración para ecosistema SSRS: resultados del modelo, predicciones y puntajes de riesgo",
            "Integración",
            "🟡",
            ["ssrs/schema_sql_server.sql", "ssrs/ReporteRiesgoFavoritismo.rdl", "ssrs/ReporteRiesgoFraccionamiento.rdl", "outputs/ssrs_publicacion_manifest.json"],
            "Contrato SQL/RDL y publicación stand-in verificados; el despliegue literal requiere CGR-DEP-05 y CGR-DEP-06.",
            deps("CGR-DEP-05", "CGR-DEP-06"),
            ok("ssrs/schema_sql_server.sql", "ssrs/ReporteRiesgoFavoritismo.rdl", "ssrs/ReporteRiesgoFraccionamiento.rdl", "outputs/ssrs_publicacion_manifest.json"),
        ),
        item(
            8,
            "Documentación de linaje y diccionario de datos desde la fuente hasta el modelo final",
            "Documentación Técnica",
            "✅",
            ["outputs/linaje_datos.csv", "data/diccionario_datos.csv", "outputs/run_manifest.json"],
            "Linaje técnico del PoC cubierto; al desplegar, los nodos locales se sustituyen por fuentes institucionales.",
            verificacion=ok("outputs/linaje_datos.csv", "data/diccionario_datos.csv", "outputs/run_manifest.json"),
        ),
        item(
            9,
            "Hiperparámetros de los modelos y sus explicaciones",
            "Analítica Avanzada",
            "✅",
            [
                "outputs/tuning_favoritismo_spark_resumen.json",
                "outputs/tuning_fraccionamiento_spark_resumen.json",
                "outputs/model_registry.json",
                "outputs/tuning_favoritismo_resumen.json",
                "outputs/tuning_fraccionamiento_resumen.json",
            ],
            "Los hiperparámetros del champion Spark proceden de evaluaciones del mismo pipeline operacional; los benchmarks sklearn permanecen identificados como compatibilidad. Deben recalibrarse con datos institucionales.",
            verificacion=ok(
                "outputs/tuning_favoritismo_spark_resumen.json",
                "outputs/tuning_fraccionamiento_spark_resumen.json",
                "outputs/model_registry.json",
            ),
        ),
        item(
            10,
            "Reporte completo de métricas de desempeño de los modelos",
            "Analítica Avanzada",
            "✅",
            [
                "outputs/tuning_favoritismo_spark_resumen.json",
                "outputs/tuning_fraccionamiento_spark_resumen.json",
                "outputs/comparacion_modelos_favoritismo.json",
                "outputs/tuning_fraccionamiento_resumen.json",
                "reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx",
            ],
            "Métricas CV/holdout del champion Spark y benchmarks de compatibilidad están versionadas; no se presentan como desempeño productivo.",
            verificacion=ok(
                "outputs/tuning_favoritismo_spark_resumen.json",
                "outputs/tuning_fraccionamiento_spark_resumen.json",
                "outputs/comparacion_modelos_favoritismo.json",
            ),
        ),
        item(
            11,
            "Oportunidades de mejora para la evolución del modelo",
            "Valor de Negocio",
            "✅",
            ["reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx", "README.md"],
            "Las recomendaciones están documentadas; su priorización institucional corresponde a la etapa de despliegue/operación.",
            verificacion=ok("reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx", "README.md"),
        ),
    ]
    return items


def main():
    items = construir()
    counts = Counter(x["estado"] for x in items)
    payload = {
        "schema_version": 2,
        "fuente": "Anexo N.º 03 del TDR público del Proyecto Interno 1.8.2, mayo de 2026",
        "catalogo_dependencias": "outputs/dependencias_cgr.json",
        "leyenda": {
            "✅": "cubierto por evidencia verificable del PoC",
            "🟡": "PoC parcial / cierre literal requiere información o validación institucional",
            "🔵": "dependencia institucional CGR",
            "🔴": "brecha técnica cerrable en el repositorio",
        },
        "resumen": dict(counts),
        "criterios": items,
        "nota_performance": "El TDR público provisto no incluye valores numéricos de los umbrales mínimos del criterio 4; el repositorio no inventa dichos valores.",
        "conclusion": "No deben existir criterios 🔴 para considerar cerrado el trabajo realizable fuera de CGR.",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lineas = [
        "# Auditoría final — Anexo N.º 03 del TDR",
        "",
        "> Prototipo independiente. Esta matriz separa evidencia reproducible del PoC de los requisitos que solo pueden cerrarse dentro de la infraestructura y gobierno de la CGR.",
        "",
        "Las dependencias institucionales se definen una sola vez en `docs/Dependencias_Institucionales_CGR.md` y se referencian aquí mediante IDs `CGR-DEP-XX`.",
        "",
        "## Leyenda",
        "",
        "- ✅ cubierto por evidencia verificable del PoC.",
        "- 🟡 PoC parcial; el cierre literal requiere información o validación institucional.",
        "- 🔵 dependencia institucional CGR.",
        "- 🔴 brecha técnica cerrable en este repositorio.",
        "",
        "## Checklist",
        "",
        "| N.º | Estado | Criterio | Evidencia en repo | Dependencias CGR | Residual |",
        "|---:|:---:|---|---|---|---|",
    ]
    for x in items:
        evidencia = "<br>".join(f"`{p}`" for p in x["evidencia_repo"])
        referencias = "<br>".join(x["dependencias_cgr"]) or "—"
        lineas.append(f"| {x['numero']} | {x['estado']} | {x['criterio']} | {evidencia} | {referencias} | {x['residual']} |")

    lineas += [
        "",
        "## Resultado",
        "",
        f"- ✅: {counts.get('✅', 0)} criterios.",
        f"- 🟡: {counts.get('🟡', 0)} criterios.",
        f"- 🔵: {counts.get('🔵', 0)} criterios.",
        f"- 🔴: {counts.get('🔴', 0)} criterios.",
        "",
        "**Criterio 4:** el TDR público provisto exige superar umbrales mínimos de Accuracy, F1-Score y AUC-ROC, pero no consigna sus valores numéricos. Por ello esta auditoría no inventa umbrales ni declara conformidad cuantitativa institucional.",
        "",
        "El objetivo de cierre externo se considera alcanzado únicamente si el conteo 🔴 es cero. Los estados 🟡/🔵 deben mantenerse visibles hasta disponer de la evidencia definida en el catálogo CGR.",
        "",
    ]
    OUT_MD.write_text("\n".join(lineas), encoding="utf-8")

    if counts.get("🔴", 0):
        raise SystemExit(f"Checklist Anexo 3 conserva {counts['🔴']} brecha(s) técnica(s) roja(s)")

    print(f"Checklist Anexo 3 generado: {counts.get('✅', 0)} ✅, {counts.get('🟡', 0)} 🟡, {counts.get('🔵', 0)} 🔵, 0 🔴")


if __name__ == "__main__":
    main()
