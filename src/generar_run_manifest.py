"""Genera ``outputs/run_manifest.json`` con trazabilidad de la ejecución.

Parámetros, versiones, hashes y resultados quedan en evidencia machine-readable.
Etapa 5B separa la metadata variable de ejecución (timestamp/duración) de una
huella reproducible estable basada en dependencias, configuración, código clave
y datasets materializados del benchmark.
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
    "data/pagos_siaf_sintetico.csv",
    "lakehouse/bronce/pagos_siaf_sintetico.csv",
    "lakehouse/plata/contratos_procesados.csv",
    "lakehouse/plata/dataset_favoritismo.csv",
    "lakehouse/plata/dataset_fraccionamiento.csv",
    "outputs/analisis_pagos_modalidades.json",
    "outputs/resumen_pagos_contrato.csv",
    "outputs/resumen_modalidades_regimen.csv",
    "outputs/comparacion_modelos_favoritismo.json",
    "outputs/tuning_favoritismo_resumen.json",
    "outputs/tuning_fraccionamiento_resumen.json",
    "outputs/ranking_riesgo_favoritismo.csv",
    "outputs/ranking_riesgo_fraccionamiento.csv",
    "outputs/ranking_vinculos_proveedor_funcionario.csv",
    "outputs/spark_favoritismo_resumen.json",
    "outputs/spark_fraccionamiento_resumen.json",
    "outputs/graphframes_resumen.json",
    "outputs/ranking_riesgo_favoritismo_spark.csv",
    "outputs/ranking_riesgo_fraccionamiento_spark.csv",
    "outputs/vinculos_graphframes_sospechosos.csv",
    "outputs/vinculos_graphframes_pagerank.csv",
    "lakehouse/oro/resumen_pagos_contrato.csv",
    "lakehouse/oro/resumen_modalidades_regimen.csv",
    "data/diccionario_datos.csv",
    "outputs/linaje_datos.csv",
]

# Solo entradas estables. No se incluyen timestamps, tiempos de ejecución ni
# outputs que incorporen esos campos; así dos corridas equivalentes pueden
# compararse mediante esta huella aunque se ejecuten en momentos distintos.
REPRODUCIBILITY_INPUTS = [
    "requirements.txt",
    "reporte/package-lock.json",
    "config/local.yaml",
    "config/local-training.yaml",
    "src/generar_datos.py",
    "src/generar_pagos_sinteticos.py",
    "src/preprocesamiento.py",
    "src/core/objeto_similarity.py",
    "src/core/fingerprints.py",
    "src/spark/evaluar_favoritismo_spark.py",
    "src/spark/evaluar_fraccionamiento_spark.py",
    "src/spark/entrenar_candidato_spark.py",
    "src/spark/score_inference_spark.py",
    "data/contratos_siaf_seace.csv",
    "data/pagos_siaf_sintetico.csv",
]

PAQUETES = [
    "pandas", "numpy", "scikit-learn", "shap", "pyspark", "delta-spark", "graphframes-py", "graphviz"
]


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


def construir_huella_reproducible(entorno: dict) -> dict:
    archivos = {}
    faltantes = []
    for relativo in REPRODUCIBILITY_INPUTS:
        ruta = ROOT / relativo
        if not ruta.exists():
            faltantes.append(relativo)
            continue
        archivos[relativo] = sha256(ruta)
    if faltantes:
        raise FileNotFoundError(
            "Faltan entradas de reproducibilidad: " + ", ".join(sorted(faltantes))
        )
    payload = {
        "schema_version": 1,
        "environment": entorno,
        "inputs_sha256": archivos,
    }
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return {
        **payload,
        "algorithm": "sha256",
        "fingerprint_sha256": hashlib.sha256(canonical).hexdigest(),
        "excludes_execution_metadata": ["generado_utc", "duracion_s"],
    }


def main():
    artefactos = {}
    for relativo in ARCHIVOS_TRAZADOS:
        ruta = ROOT / relativo
        artefactos[relativo] = {
            "existe": ruta.exists(),
            "sha256": sha256(ruta) if ruta.exists() else None,
            "bytes": ruta.stat().st_size if ruta.exists() else None,
        }

    entorno = versiones()
    manifest = {
        "schema_version": 4,
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_sha(),
        "entorno": entorno,
        "reproducibility": construir_huella_reproducible(entorno),
        "arquitectura_datos": {
            "entrada_modelos": "lakehouse/plata",
            "salida_reporting": "lakehouse/oro",
            "benchmark_metodologico": "scikit-learn",
            "implementacion_objetivo_tdr": "Apache Spark MLlib / GraphFrames",
            "analisis_pagos_modalidades": "contrato canónico contracts + payments; evidencia sintética",
            "nota": "simulación local; no equivale al Lakehouse ni clúster institucional CGR",
        },
        "analisis_pagos_modalidades": cargar_json_relativo("outputs/analisis_pagos_modalidades.json"),
        "comparacion_modelos_favoritismo": cargar_json_relativo(
            "outputs/comparacion_modelos_favoritismo.json"
        ),
        "tuning_favoritismo": cargar_json_relativo("outputs/tuning_favoritismo_resumen.json"),
        "tuning_fraccionamiento": cargar_json_relativo("outputs/tuning_fraccionamiento_resumen.json"),
        "spark_favoritismo": cargar_json_relativo("outputs/spark_favoritismo_resumen.json"),
        "spark_fraccionamiento": cargar_json_relativo("outputs/spark_fraccionamiento_resumen.json"),
        "graphframes": cargar_json_relativo("outputs/graphframes_resumen.json"),
        "validacion_p0_datos_reales": cargar_json_relativo("outputs/validacion_p0_datos_reales.json"),
        "artefactos": artefactos,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(
        f"Manifest generado: {OUTPUT.relative_to(ROOT)} | "
        f"reproducibility={manifest['reproducibility']['fingerprint_sha256']}"
    )
    return manifest


if __name__ == "__main__":
    main()
