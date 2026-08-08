"""Auditoría integral del TDR público — Sprint 4.

Amplía el checklist del Anexo 3 hacia el cuerpo completo del TDR. La auditoría
no convierte dependencias institucionales en defectos del repositorio:

✅ cubierto por evidencia reproducible del PoC;
🟡 PoC demostrable, cierre literal requiere CGR;
🔵 actividad/aceptación enteramente institucional;
🔴 brecha técnica que todavía puede cerrarse desde este repositorio.

Toda fila 🟡/🔵 debe referenciar el catálogo canónico CGR-DEP-01..08.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from dependencias_cgr import POR_ID, validar_catalogo

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "outputs" / "auditoria_tdr_completo.json"
OUT_MD = ROOT / "docs" / "Auditoria_TDR_Completo.md"


def existe(rel: str) -> bool:
    p = ROOT / rel
    return p.exists() and (not p.is_file() or p.stat().st_size > 0)


def leer_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def criterio_tecnico(numero, seccion, requisito, evidencias, detalle):
    ok = all(existe(e) for e in evidencias)
    return {
        "numero": numero,
        "seccion_tdr": seccion,
        "requisito": requisito,
        "estado": "✅" if ok else "🔴",
        "evidencias": evidencias,
        "dependencias_cgr": [],
        "detalle": detalle if ok else "Falta al menos una evidencia técnica exigible desde el repositorio.",
    }


def criterio_parcial(numero, seccion, requisito, evidencias, deps, detalle):
    ok = all(existe(e) for e in evidencias)
    return {
        "numero": numero,
        "seccion_tdr": seccion,
        "requisito": requisito,
        "estado": "🟡" if ok else "🔴",
        "evidencias": evidencias,
        "dependencias_cgr": deps,
        "detalle": detalle if ok else "La parte demostrable por PoC no está completa todavía.",
    }


def criterio_institucional(numero, seccion, requisito, deps, detalle):
    return {
        "numero": numero,
        "seccion_tdr": seccion,
        "requisito": requisito,
        "estado": "🔵",
        "evidencias": [],
        "dependencias_cgr": deps,
        "detalle": detalle,
    }


def construir_criterios() -> list[dict]:
    return [
        criterio_tecnico(
            1, "4.1.1 / 6", "Análisis Exploratorio de Datos (EDA) y estadísticas descriptivas",
            ["outputs/evidencia_documental.json", "outputs/charts"],
            "EDA, estadísticas y gráficos programáticos forman parte de la evidencia reproducible.",
        ),
        criterio_parcial(
            2, "4.1.2-4.1.3 / 6", "Identificación, adquisición, integración y consolidación SIAF/SEACE",
            ["docs/Integracion_Datos.md", "config/cgr.example.yaml", "src/core/schemas.py"],
            ["CGR-DEP-01", "CGR-DEP-06"],
            "Existe contrato canónico y conectores; la lectura de fuentes internas reales requiere acceso CGR.",
        ),
        criterio_tecnico(
            3, "4.1.4 / Productos 2 y 5", "Limpieza, faltantes, outliers, codificación y normalización/estandarización",
            ["src/preprocesamiento.py", "outputs/champions_spark/preprocesador_contratos.json"],
            "FIT/TRANSFORM están separados; el P99 se congela y el serving de favoritismo consume monto_capped.",
        ),
        criterio_tecnico(
            4, "4.1.5", "Enriquecimiento y generación de características",
            ["data/dataset_favoritismo.csv", "data/dataset_fraccionamiento.csv", "outputs/linaje_datos.csv"],
            "Features de favoritismo/fraccionamiento y linaje fuente→feature están materializados.",
        ),
        criterio_tecnico(
            5, "6", "Análisis Profundo de Pagos y Modalidades de Contratación",
            [
                "data/pagos_siaf_sintetico.csv",
                "outputs/analisis_pagos_modalidades.json",
                "outputs/resumen_pagos_contrato.csv",
                "outputs/resumen_modalidades_regimen.csv",
                "outputs/charts/11_ratio_pago_contrato.png",
                "outputs/charts/12_modalidades_regimen.png",
            ],
            "Se analizan patrones sintéticos de pagos, montos y modalidades; la sustitución por pagos SIAF reales depende de CGR.",
        ),
        criterio_tecnico(
            6, "4.2.2 / Productos 3-4", "Identificación de proveedores favoritos",
            ["outputs/comparacion_modelos_favoritismo.json", "outputs/tuning_favoritismo_resumen.json", "outputs/ranking_riesgo_favoritismo_spark.csv"],
            "Clasificación/riesgo con benchmark, tuning, explicación y ejecución Spark.",
        ),
        criterio_tecnico(
            7, "4.2.3 / Productos 6-7", "Detección de fraccionamiento y compras repetitivas/anómalas",
            ["outputs/tuning_fraccionamiento_resumen.json", "outputs/ranking_riesgo_fraccionamiento_spark.csv"],
            "Isolation Forest de referencia + KMeans MLlib + señal interpretable por ventana/cuxtía.",
        ),
        criterio_tecnico(
            8, "4.2.4", "Evaluación de vínculos proveedor-funcionario mediante grafos/redes",
            ["outputs/graphframes_resumen.json", "outputs/vinculos_graphframes_sospechosos.csv"],
            "GraphFrames se ejecuta sobre escenario sintético; datos personales reales no se publican.",
        ),
        criterio_tecnico(
            9, "4.2.5", "Entrenamiento, validación cruzada y optimización de hiperparámetros",
            ["outputs/tuning_favoritismo_resumen.json", "outputs/tuning_fraccionamiento_resumen.json", "outputs/spark_favoritismo_resumen.json"],
            "Tuning/validación y separación de holdout quedan persistidos.",
        ),
        criterio_parcial(
            10, "3.2.a / 4.2.6", "Apache Spark MLlib escalable y pruebas de rendimiento/robustez",
            ["outputs/inference_spark_smoke_summary.json", "outputs/spark_favoritismo_resumen.json", "outputs/spark_fraccionamiento_resumen.json"],
            ["CGR-DEP-06", "CGR-DEP-03"],
            "Spark MLlib se ejecuta en local[*]; clúster institucional y aceptación de performance requieren CGR.",
        ),
        criterio_tecnico(
            11, "4.3.1-4.3.2", "Reportes automáticos con tablas, estadísticas, gráficos y métricas",
            ["src/generar_evidencia_documental.py", "reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx", "outputs/charts"],
            "La documentación formal se genera desde evidencia machine-readable y gráficos programáticos.",
        ),
        criterio_tecnico(
            12, "4.4", "Documentación técnica completa, código fuente, diccionario y diagrama",
            ["data/diccionario_datos.csv", "outputs/charts/09_diagrama_modelo_datos.png", "outputs/run_manifest.json", "README.md"],
            "Código, versiones, hashes, diccionario, diagrama y documentación están versionados.",
        ),
        criterio_parcial(
            13, "Anexo 2 / 6", "Lakehouse Bronce/Plata/Oro y DAGs de orquestación",
            ["lakehouse/bronce", "lakehouse/plata", "lakehouse/oro", "airflow_home/dags/dag_modulo_analisis_datos.py"],
            ["CGR-DEP-01", "CGR-DEP-06"],
            "La arquitectura es funcional localmente; Datamart/HDFS/YARN/Airflow institucional requieren CGR.",
        ),
        criterio_tecnico(
            14, "3.2.c / 6", "Autoevaluación y estrategia de actualización/reentrenamiento sostenible",
            ["src/autoevaluacion.py", "src/registro_modelos.py", "docs/Train_Inference.md"],
            "El reentrenamiento produce candidate; no existe autopromoción silenciosa.",
        ),
        criterio_tecnico(
            15, "3.2.f / Productos 7-8", "Separación TRAIN/INFERENCE, persistencia y serving sin reentrenamiento",
            ["outputs/model_registry.json", "outputs/inference_spark_smoke_summary.json", "airflow_home/dags/dag_inferencia_modelos.py"],
            "El perfil activo es Spark MLlib; inference no consume labels, training ni tuning.",
        ),
        criterio_parcial(
            16, "3.2.f / 4.2.6 / 6", "Despliegue, seguridad, mantenimiento y monitorización operacional",
            ["docs/Train_Inference.md", "src/monitoreo_modelos.py", "outputs/model_registry.json"],
            ["CGR-DEP-04", "CGR-DEP-06"],
            "Controles de software existen; identidad, secretos, segregación y operación productiva son institucionales.",
        ),
        criterio_institucional(
            17, "6 / Producto 7", "Pruebas de integración en ambientes DEV/QA/PROD y puesta a producción",
            ["CGR-DEP-06", "CGR-DEP-04"],
            "No es demostrable fuera de los ambientes, accesos y controles institucionales.",
        ),
        criterio_parcial(
            18, "Anexo 3 / Producto 7", "Publicación e integración en SQL Server/SSRS",
            ["ssrs/schema_sql_server.sql", "ssrs/ReporteRiesgoFavoritismo.rdl", "ssrs/ReporteRiesgoFraccionamiento.rdl", "outputs/ssrs_publicacion_manifest.json"],
            ["CGR-DEP-05", "CGR-DEP-06"],
            "Contrato T-SQL/RDL validado localmente; despliegue real requiere SQL Server/SSRS CGR.",
        ),
        criterio_parcial(
            19, "Anexo 3 / 3.2.e", "Umbrales institucionales y validación productiva de Accuracy/F1/AUC-ROC",
            ["outputs/comparacion_modelos_favoritismo.json", "outputs/tuning_fraccionamiento_resumen.json"],
            ["CGR-DEP-03", "CGR-DEP-06"],
            "El PoC reporta métricas; el TDR público no aporta los mínimos numéricos ni ground truth institucional.",
        ),
        criterio_institucional(
            20, "6 / Producto 7", "Certificación, levantamiento de observaciones/incidencias y marcha blanca",
            ["CGR-DEP-07", "CGR-DEP-06"],
            "Requiere usuarios, casos, ambientes e incidencias reales de la CGR.",
        ),
        criterio_institucional(
            21, "6 / Producto 8", "Transferencia de conocimiento a usuarios técnicos y funcionales",
            ["CGR-DEP-08"],
            "Las sesiones y actas de transferencia son una actividad contractual institucional.",
        ),
        criterio_institucional(
            22, "13", "Accesos a bases de datos y herramientas colaborativas CGR",
            ["CGR-DEP-01", "CGR-DEP-04", "CGR-DEP-06"],
            "El repositorio no puede crear ni simular como reales permisos institucionales.",
        ),
        criterio_institucional(
            23, "14", "Entrega/propiedad/confidencialidad y repositorio institucional",
            ["CGR-DEP-08", "CGR-DEP-04"],
            "El PoC mantiene licencia/avisos propios; la cesión y entrega contractual se formalizan dentro de CGR.",
        ),
        criterio_tecnico(
            24, "Anexo 1", "Formato formal de Productos e Informe Final",
            ["reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx", "reporte/productos_formales/Producto_01_Plan_de_Trabajo.docx", "reporte/productos_formales/Producto_07_Informe_Final.docx"],
            "Los ocho DOCX son regenerados, indexados, auditados y renderizados en CI.",
        ),
        criterio_tecnico(
            25, "6 / análisis normativo", "Trazabilidad normativa por fecha/régimen para umbrales y modalidades",
            ["src/umbrales_normativos.py", "outputs/analisis_pagos_modalidades.json"],
            "El rango sintético 2023-2026 conserva fuentes oficiales versionadas y cambio de régimen 22/04/2025.",
        ),
    ]


def main():
    validar_catalogo()
    criterios = construir_criterios()

    deps_invalidas = sorted({
        dep for c in criterios for dep in c["dependencias_cgr"] if dep not in POR_ID
    })
    parciales_sin_dep = [
        c["numero"] for c in criterios
        if c["estado"] in {"🟡", "🔵"} and not c["dependencias_cgr"]
    ]
    if deps_invalidas or parciales_sin_dep:
        raise ValueError(
            f"Auditoría TDR con dependencias inválidas={deps_invalidas}, parciales_sin_dep={parciales_sin_dep}"
        )

    # Gates semánticos adicionales para evitar falsos positivos por mera existencia.
    if existe("outputs/analisis_pagos_modalidades.json"):
        pagos = leer_json("outputs/analisis_pagos_modalidades.json")
        if pagos.get("payments", {}).get("orphan_payments") != 0:
            criterios[4]["estado"] = "🔴"
            criterios[4]["detalle"] = "Existen pagos sin contrato resoluble."
        if not all(str(anio) in {str(k) for k in pagos.get("normative_provenance_2023_2026", {})} for anio in range(2023, 2027)):
            criterios[24]["estado"] = "🔴"
            criterios[24]["detalle"] = "Falta procedencia normativa 2023-2026."

    if existe("outputs/inference_spark_smoke_summary.json"):
        serving = leer_json("outputs/inference_spark_smoke_summary.json")
        if not (
            serving.get("active_serving_profile") == "spark_mllib"
            and serving.get("labels_consumed") is False
            and serving.get("training_invoked") is False
            and serving.get("tuning_invoked") is False
            and serving.get("favoritismo_amount_source") == "monto_capped"
            and serving.get("fraccionamiento_amount_source") == "monto"
        ):
            criterios[14]["estado"] = "🔴"
            criterios[14]["detalle"] = "Serving Spark no cumple el contrato TRAIN/INFERENCE de Sprint 4."

    resumen = Counter(c["estado"] for c in criterios)
    payload = {
        "schema_version": 1,
        "scope": "TDR completo público de mayo de 2026",
        "nature": "auditoría del PoC independiente; no conformidad ni aprobación CGR",
        "total_criterios": len(criterios),
        "resumen": {estado: int(resumen.get(estado, 0)) for estado in ["✅", "🟡", "🔵", "🔴"]},
        "repo_closable_gaps": int(resumen.get("🔴", 0)),
        "criterios": criterios,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lineas = [
        "# Auditoría integral del TDR público — Sprint 4",
        "",
        "> PoC independiente. Esta matriz distingue evidencia técnica reproducible de dependencias que solo pueden cerrarse con datos, infraestructura, usuarios, permisos o conformidad de la CGR.",
        "",
        "## Resumen",
        "",
        f"- ✅ Cubierto por PoC: **{payload['resumen']['✅']}**",
        f"- 🟡 PoC demostrable / cierre literal CGR: **{payload['resumen']['🟡']}**",
        f"- 🔵 Dependencia institucional: **{payload['resumen']['🔵']}**",
        f"- 🔴 Brecha cerrable desde repo: **{payload['resumen']['🔴']}**",
        "",
        "| # | Sección TDR | Estado | Requisito | Dependencias CGR |",
        "|---:|---|:---:|---|---|",
    ]
    for c in criterios:
        deps = ", ".join(c["dependencias_cgr"]) or "—"
        lineas.append(
            f"| {c['numero']} | {c['seccion_tdr']} | {c['estado']} | {c['requisito']} | {deps} |"
        )
    lineas += ["", "## Detalle", ""]
    for c in criterios:
        lineas += [
            f"### {c['numero']}. {c['requisito']} — {c['estado']}",
            "",
            c["detalle"],
            "",
            "Evidencia: " + (", ".join(f"`{e}`" for e in c["evidencias"]) or "actividad institucional"),
            "",
        ]
    OUT_MD.write_text("\n".join(lineas), encoding="utf-8")

    if payload["repo_closable_gaps"]:
        rojos = [str(c["numero"]) for c in criterios if c["estado"] == "🔴"]
        raise SystemExit(f"TDR completo mantiene brechas cerrables en repo: {', '.join(rojos)}")
    print(
        "TDR completo sin brechas rojas cerrables exclusivamente desde el repo: "
        f"✅={payload['resumen']['✅']} 🟡={payload['resumen']['🟡']} "
        f"🔵={payload['resumen']['🔵']} 🔴=0"
    )
    return payload


if __name__ == "__main__":
    main()
