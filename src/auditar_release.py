"""Auditoría de coherencia previa al release candidate del PoC independiente."""

from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path

from dependencias_cgr import DEPENDENCIAS_CGR, POR_ID, validar_catalogo

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "outputs" / "auditoria_release.json"
OUT_MD = ROOT / "docs" / "Auditoria_Final_Release.md"


def leer_json(ruta: str):
    return json.loads((ROOT / ruta).read_text(encoding="utf-8"))


def cabecera_csv(ruta: str) -> list[str]:
    with (ROOT / ruta).open(encoding="utf-8", newline="") as f:
        return next(csv.reader(f))


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "no-disponible"


def main():
    validar_catalogo()
    checks: list[dict] = []

    def check(nombre: str, condicion: bool, detalle: str):
        checks.append({"check": nombre, "ok": bool(condicion), "detalle": detalle})

    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    check(
        "versión semántica release candidate",
        bool(re.fullmatch(r"\d+\.\d+\.\d+-rc\.\d+", version)),
        version,
    )

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    release_notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    check(
        "disclaimer público explícito",
        "Prototipo independiente" in readme and "no constituye una implementación" in readme.lower(),
        "README distingue el PoC de una implementación oficial",
    )
    check(
        "release no se presenta como oficial",
        "No es una versión oficial de la CGR" in release_notes,
        "RELEASE_NOTES mantiene el alcance independiente",
    )

    checklist = leer_json("outputs/checklist_anexo3.json")
    resumen = checklist["resumen"]
    check(
        "Anexo 3 sin brechas rojas",
        resumen.get("🔴", 0) == 0,
        f"✅={resumen.get('✅', 0)}, 🟡={resumen.get('🟡', 0)}, 🔵={resumen.get('🔵', 0)}, 🔴={resumen.get('🔴', 0)}",
    )
    check(
        "distribución esperada del checklist",
        resumen.get("✅", 0) == 6 and resumen.get("🟡", 0) == 4 and resumen.get("🔵", 0) == 1,
        "6 ✅ / 4 🟡 / 1 🔵",
    )
    deps_referenciadas = {
        dep
        for c in checklist["criterios"]
        for dep in c.get("dependencias_cgr", [])
    }
    deps_invalidas = sorted(deps_referenciadas - set(POR_ID))
    parciales_sin_dep = [
        c["numero"] for c in checklist["criterios"]
        if c["estado"] in {"🟡", "🔵"} and not c.get("dependencias_cgr")
    ]
    check(
        "checklist enlazado al catálogo CGR",
        not deps_invalidas and not parciales_sin_dep,
        f"referencias={sorted(deps_referenciadas)}",
    )

    deps_json = leer_json("outputs/dependencias_cgr.json")
    check(
        "catálogo institucional único",
        deps_json["total"] == len(DEPENDENCIAS_CGR) == 8,
        "8 dependencias canónicas CGR-DEP-01..08",
    )

    ssrs = leer_json("outputs/ssrs_publicacion_manifest.json")
    conteos = ssrs["validacion"]["conteos_tablas"]
    check(
        "contrato SSRS local verificado",
        all(conteos.get(t, 0) > 0 for t in [
            "PrediccionesFavoritismo",
            "PrediccionesFraccionamiento",
            "VinculosProveedorFuncionario",
        ]),
        str(conteos),
    )
    check(
        "dos RDL de riesgo presentes",
        (ROOT / "ssrs/ReporteRiesgoFavoritismo.rdl").exists()
        and (ROOT / "ssrs/ReporteRiesgoFraccionamiento.rdl").exists()
        and (ROOT / "ssrs/schema_sql_server.sql").exists(),
        "favoritismo + fraccionamiento + DDL T-SQL",
    )

    fav = leer_json("outputs/comparacion_modelos_favoritismo.json")
    frac = leer_json("outputs/tuning_fraccionamiento_resumen.json")
    check(
        "Accuracy/F1/AUC-ROC reportados en favoritismo",
        all(k in fav["resultados"][0] for k in ["accuracy", "f1", "auc_roc"]),
        "Accuracy se reporta sin desplazar AUC-PR como criterio primario",
    )
    check(
        "Accuracy/F1/AUC-ROC reportados en fraccionamiento",
        all(k in frac["metricas_holdout_final"] for k in ["accuracy", "f1", "auc_roc"]),
        "holdout final independiente",
    )

    cols_frac = cabecera_csv("outputs/ranking_riesgo_fraccionamiento.csv")
    cols_fav = cabecera_csv("outputs/ranking_riesgo_favoritismo.csv")
    check(
        "nomenclatura canónica de fraccionamiento",
        "senal_priorizacion_fraccionamiento" in cols_frac
        and "cumple_regla_fraccionamiento" not in cols_frac,
        "senal_priorizacion_fraccionamiento",
    )
    check(
        "modalidades de favoritismo separadas",
        "pct_contratacion_directa" in cols_fav
        and "pct_comparacion_precios" in cols_fav
        and "pct_no_competitiva" not in cols_fav,
        "Contratación Directa != Comparación de Precios",
    )

    oro = {p.name for p in (ROOT / "lakehouse/oro").glob("*.csv")}
    check(
        "Oro sin datasets intermedios",
        "dataset_favoritismo.csv" not in oro and "dataset_fraccionamiento.csv" not in oro,
        f"artefactos Oro={len(oro)}",
    )

    reales_versionados = list((ROOT / "data_real").glob("*.csv")) + list((ROOT / "outputs").glob("*_REAL.csv"))
    check(
        "sin derivados reales identificables versionados",
        len(reales_versionados) == 0,
        "raw/derivados reales identificables permanecen fuera del repositorio",
    )

    docs = [ROOT / "reporte/Reporte_Tecnico_Prototipo_CGR_1.8.2.docx"] + sorted(
        (ROOT / "reporte/productos_formales").glob("Producto_*.docx")
    )
    check(
        "documentación formal completa",
        len(docs) == 8 and all(p.exists() and p.stat().st_size > 0 for p in docs),
        f"{len(docs)} DOCX (7 productos + informe final)",
    )

    manifest = leer_json("outputs/run_manifest.json")
    entorno = manifest.get("entorno", {})
    check(
        "manifiesto reproducible Spark/GraphFrames",
        manifest.get("schema_version") == 3
        and entorno.get("pyspark") == "4.1.1"
        and entorno.get("graphframes-py") == "0.10.0",
        f"commit evidencia={manifest.get('git_commit')}",
    )

    canonicos = [
        ROOT / "README.md",
        ROOT / "docs/Checklist_Anexo_03.md",
        ROOT / "docs/Dependencias_Institucionales_CGR.md",
        ROOT / "data/diccionario_datos.csv",
    ]
    texto_canonico = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in canonicos if p.exists()).lower()
    check(
        "sin residuos de nomenclatura obsoleta en artefactos canónicos",
        all(token not in texto_canonico for token in [
            "pct_no_competitiva",
            "cumple_regla_fraccionamiento",
            "47,442",
        ]),
        "nomenclatura y conteos vigentes",
    )

    check("licencia presente", (ROOT / "LICENSE").exists(), "MIT para el código del PoC")

    fallos = [c for c in checks if not c["ok"]]
    payload = {
        "schema_version": 1,
        "version": version,
        "git_commit_auditado": git_head(),
        "naturaleza": "release candidate del PoC público independiente; no aprobación CGR",
        "total_checks": len(checks),
        "checks_ok": len(checks) - len(fallos),
        "checks_fallidos": len(fallos),
        "release_ready": not fallos,
        "checks": checks,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lineas = [
        f"# Auditoría final de release — v{version}",
        "",
        "> Release candidate del PoC independiente. `release_ready=true` significa coherencia técnica del repositorio, **no conformidad ni aprobación institucional de la CGR**.",
        "",
        f"- Commit auditado: `{payload['git_commit_auditado']}`",
        f"- Checks: **{payload['checks_ok']}/{payload['total_checks']} OK**",
        f"- Resultado: **{'READY' if payload['release_ready'] else 'NO READY'}**",
        "",
        "| Estado | Verificación | Detalle |",
        "|:---:|---|---|",
    ]
    for c in checks:
        lineas.append(f"| {'✅' if c['ok'] else '🔴'} | {c['check']} | {c['detalle']} |")
    lineas += [
        "",
        "## Pendientes después del release",
        "",
        "No se trasladan aquí como brechas técnicas. La única fuente canónica es `docs/Dependencias_Institucionales_CGR.md` (`CGR-DEP-01..08`).",
        "",
    ]
    OUT_MD.write_text("\n".join(lineas), encoding="utf-8")

    if fallos:
        nombres = ", ".join(c["check"] for c in fallos)
        raise SystemExit(f"Release NO READY. Fallos: {nombres}")
    print(f"Release READY: {len(checks)}/{len(checks)} checks OK para v{version}")


if __name__ == "__main__":
    main()
