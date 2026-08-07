"""Genera `outputs/run_manifest.json` con trazabilidad de la ejecución.

Objetivo: que parámetros, versiones, hashes y resultados referenciados por la
documentación provengan de evidencia machine-readable y no de números copiados
a mano. Es un PoC local del linaje/documentación exigidos por el TDR.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "run_manifest.json"

ARCHIVOS_TRAZADOS = [
    "lakehouse/plata/contratos_procesados.csv",
    "lakehouse/plata/dataset_favoritismo.csv",
    "lakehouse/plata/dataset_fraccionamiento.csv",
    "outputs/tuning_favoritismo_resumen.json",
    "outputs/tuning_fraccionamiento_resumen.json",
    "outputs/ranking_riesgo_favoritismo.csv",
    "outputs/ranking_riesgo_fraccionamiento.csv",
    "outputs/ranking_vinculos_proveedor_funcionario.csv",
]
PAQUETES = ["pandas", "numpy", "scikit-learn", "shap", "pyspark"]


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def git_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def versiones():
    resultado = {"python": platform.python_version()}
    for paquete in PAQUETES:
        try:
            resultado[paquete] = importlib.metadata.version(paquete)
        except importlib.metadata.PackageNotFoundError:
            resultado[paquete] = None
    return resultado


def cargar_json_relativo(ruta_relativa):
    ruta = ROOT / ruta_relativa
    if not ruta.exists():
        return None
    with ruta.open(encoding="utf-8") as f:
        return json.load(f)


def main():
    artefactos = {}
    for relativo in ARCHIVOS_TRAZADOS:
        ruta = ROOT / relativo
        artefactos[relativo] = {
            "existe": ruta.exists(),
            "sha256": sha256(ruta) if ruta.exists() else None,
            "bytes": ruta.stat().st_size if ruta.exists() else None,
        }

    manifest = {
        "schema_version": 1,
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_sha(),
        "entorno": versiones(),
        "arquitectura_datos": {
            "entrada_modelos": "lakehouse/plata",
            "salida_reporting": "lakehouse/oro",
            "nota": "simulación local; no equivale al Lakehouse institucional CGR",
        },
        "tuning_favoritismo": cargar_json_relativo("outputs/tuning_favoritismo_resumen.json"),
        "tuning_fraccionamiento": cargar_json_relativo("outputs/tuning_fraccionamiento_resumen.json"),
        "validacion_p0_datos_reales": cargar_json_relativo("outputs/validacion_p0_datos_reales.json"),
        "artefactos": artefactos,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Manifest generado: {OUTPUT.relative_to(ROOT)}")
    return manifest


if __name__ == "__main__":
    main()
