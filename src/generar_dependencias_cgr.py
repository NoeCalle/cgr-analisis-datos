"""Genera la matriz única de dependencias institucionales CGR."""

from __future__ import annotations

import json
from pathlib import Path

from dependencias_cgr import DEPENDENCIAS_CGR, validar_catalogo

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "outputs" / "dependencias_cgr.json"
OUT_MD = ROOT / "docs" / "Dependencias_Institucionales_CGR.md"


def main():
    validar_catalogo()
    payload = {
        "schema_version": 1,
        "naturaleza": "Dependencias institucionales no cerrables desde el PoC público independiente",
        "total": len(DEPENDENCIAS_CGR),
        "dependencias": DEPENDENCIAS_CGR,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lineas = [
        "# Dependencias institucionales CGR",
        "",
        "> Fuente canónica de pendientes que **no pueden cerrarse desde este repositorio público independiente**. No deben convertirse en simulaciones destinadas a aparentar cumplimiento institucional.",
        "",
        "| ID | Dependencia | Tipo | Qué falta para cerrarla | Criterios/etapa afectada |",
        "|---|---|---|---|---|",
    ]
    for d in DEPENDENCIAS_CGR:
        afecta = ", ".join(str(x) for x in d["afecta"])
        lineas.append(
            f"| {d['id']} | {d['nombre']} | {d['tipo']} | {d['evidencia_para_cierre']} | {afecta} |"
        )

    lineas += [
        "",
        "## Regla de cierre",
        "",
        "Una dependencia solo cambia de estado cuando existe la evidencia institucional indicada. La existencia de un stand-in local, datos sintéticos o una configuración placeholder **no sustituye** esa evidencia.",
        "",
        "## Alcance del release candidate",
        "",
        "El release candidate del PoC puede considerarse técnicamente cerrado con estas dependencias abiertas, siempre que la auditoría del Anexo 3 mantenga **0 brechas rojas (🔴)**. Los estados 🟡/🔵 siguen visibles hasta la ejecución dentro de CGR.",
        "",
    ]
    OUT_MD.write_text("\n".join(lineas), encoding="utf-8")
    print(f"Matriz CGR generada: {len(DEPENDENCIAS_CGR)} dependencias institucionales")


if __name__ == "__main__":
    main()
