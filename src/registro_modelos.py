"""Registro mínimo de modelos para separar TRAIN, promoción e INFERENCE.

No pretende sustituir un registry institucional (MLflow u otro). En el PoC
proporciona un contrato verificable:

TRAIN -> candidate manifest (runtime) -> promoción explícita -> champion registry
                                              |
                                              +-- nunca aprobación CGR

INFERENCE solo carga artefactos declarados como champion y comprueba SHA-256.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

REGISTRY_SCHEMA_VERSION = 1
DEFAULT_REGISTRY = Path("outputs/model_registry.json")
CHAMPION_DIR = Path("outputs/champions")

DESTINOS = {
    "preprocessor": CHAMPION_DIR / "preprocesador_contratos.joblib",
    "favoritismo_model": CHAMPION_DIR / "modelo_favoritismo_rf.joblib",
    "fraccionamiento_model": CHAMPION_DIR / "modelo_fraccionamiento_isoforest.joblib",
    "fraccionamiento_scaler": CHAMPION_DIR / "scaler_fraccionamiento.joblib",
}


def sha256_archivo(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def guardar_json_determinista(path: str | Path, payload: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def cargar_manifest_candidato(path: str | Path) -> dict:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise ValueError("Manifest candidato incompatible.")
    if data.get("status") != "candidate":
        raise ValueError("El manifest indicado no representa un modelo candidato.")
    requeridos = set(DESTINOS)
    artefactos = data.get("artifacts", {})
    faltantes = requeridos - set(artefactos)
    if faltantes:
        raise ValueError(f"Manifest candidato incompleto; faltan artefactos: {sorted(faltantes)}")
    for nombre in requeridos:
        ruta = Path(artefactos[nombre]["path"])
        if not ruta.exists():
            raise FileNotFoundError(f"Artefacto candidato no existe: {ruta}")
        esperado = artefactos[nombre]["sha256"]
        actual = sha256_archivo(ruta)
        if actual != esperado:
            raise ValueError(f"SHA-256 no coincide para candidato {nombre}: {ruta}")
    return data


def promover_candidato(
    manifest_path: str | Path,
    *,
    approved_by: str,
    acknowledge_poc_only: bool,
    registry_path: str | Path = DEFAULT_REGISTRY,
) -> dict:
    """Copia un candidato validado al conjunto champion del PoC.

    La bandera explícita evita que un llamado accidental parezca una aprobación
    institucional. Esta promoción solo significa que CI/operador del PoC eligió
    qué artefacto usa el smoke de inference.
    """
    if not acknowledge_poc_only:
        raise ValueError(
            "Promoción bloqueada: debe reconocer explícitamente que es solo para el PoC "
            "y no constituye aprobación institucional CGR."
        )
    if not approved_by or not approved_by.strip():
        raise ValueError("approved_by es obligatorio para registrar la promoción del PoC.")

    candidato = cargar_manifest_candidato(manifest_path)
    CHAMPION_DIR.mkdir(parents=True, exist_ok=True)

    artefactos_champion = {}
    for nombre, destino in DESTINOS.items():
        origen = Path(candidato["artifacts"][nombre]["path"])
        shutil.copy2(origen, destino)
        artefactos_champion[nombre] = {
            "path": destino.as_posix(),
            "sha256": sha256_archivo(destino),
        }

    registry = {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "status": "champion",
        "champion_id": candidato["candidate_id"],
        "nature": "PoC público independiente; no constituye aprobación ni despliegue CGR",
        "promotion": {
            "trigger": "explicit_command",
            "approved_by": approved_by.strip(),
            "scope": "poc_technical_serving",
            "institutional_approval": False,
        },
        "training": candidato["training"],
        "models": candidato["models"],
        "artifacts": artefactos_champion,
    }
    guardar_json_determinista(registry_path, registry)
    return registry


def cargar_registry_champion(path: str | Path = DEFAULT_REGISTRY) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"No existe registry champion {path}. TRAIN no habilita serving por sí mismo: "
            "se requiere promoción explícita."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != REGISTRY_SCHEMA_VERSION or data.get("status") != "champion":
        raise ValueError(f"Registry champion incompatible o inválido: {path}")
    if data.get("promotion", {}).get("institutional_approval") is not False:
        raise ValueError("El registry PoC no debe declarar aprobación institucional.")

    for nombre, spec in data.get("artifacts", {}).items():
        ruta = Path(spec["path"])
        if not ruta.exists():
            raise FileNotFoundError(f"Artefacto champion ausente ({nombre}): {ruta}")
        actual = sha256_archivo(ruta)
        if actual != spec["sha256"]:
            raise ValueError(f"Integridad SHA-256 falló para champion {nombre}: {ruta}")
    return data
