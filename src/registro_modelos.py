"""Registry técnico unificado para TRAIN, promoción e INFERENCE.

El PoC mantiene dos perfiles diferenciados dentro de un único registry:
- ``sklearn``: benchmark/serving de compatibilidad;
- ``spark_mllib``: serving objetivo alineado a la arquitectura del TDR.

La promoción siempre es explícita y nunca implica aprobación institucional CGR.
Los artefactos pueden ser archivos o directorios Spark y se verifican por SHA-256.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

CANDIDATE_SCHEMA_VERSION = 1
REGISTRY_SCHEMA_VERSION = 2
DEFAULT_REGISTRY = Path("outputs/model_registry.json")

SKLEARN_PROFILE = "sklearn"
SPARK_PROFILE = "spark_mllib"

SKLEARN_CHAMPION_DIR = Path("outputs/champions")
SPARK_CHAMPION_DIR = Path("outputs/champions_spark")

SKLEARN_DESTINOS = {
    "preprocessor": SKLEARN_CHAMPION_DIR / "preprocesador_contratos.joblib",
    "preprocessor_json": SKLEARN_CHAMPION_DIR / "preprocesador_contratos.json",
    "favoritismo_model": SKLEARN_CHAMPION_DIR / "modelo_favoritismo_rf.joblib",
    "fraccionamiento_model": SKLEARN_CHAMPION_DIR / "modelo_fraccionamiento_isoforest.joblib",
    "fraccionamiento_scaler": SKLEARN_CHAMPION_DIR / "scaler_fraccionamiento.joblib",
}
SKLEARN_REQUERIDOS = {
    "preprocessor",
    "favoritismo_model",
    "fraccionamiento_model",
    "fraccionamiento_scaler",
}

SPARK_DESTINOS = {
    "preprocessor_json": SPARK_CHAMPION_DIR / "preprocesador_contratos.json",
    "preprocessor_medians": SPARK_CHAMPION_DIR / "medianas_monto_por_objeto",
    "favoritismo_model": SPARK_CHAMPION_DIR / "modelo_favoritismo_rf",
    "fraccionamiento_model": SPARK_CHAMPION_DIR / "modelo_fraccionamiento_kmeans",
    "fraccionamiento_scaler": SPARK_CHAMPION_DIR / "scaler_fraccionamiento",
}
# Las medianas externas son opcionales para conservar compatibilidad con
# champions entrenados desde CSV/SQL Server, cuyo mapa vive dentro del JSON.
SPARK_REQUERIDOS = {
    "preprocessor_json",
    "favoritismo_model",
    "fraccionamiento_model",
    "fraccionamiento_scaler",
}


def sha256_archivo(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_ruta(path: str | Path) -> str:
    path = Path(path)
    if path.is_file():
        return sha256_archivo(path)
    if not path.is_dir():
        raise FileNotFoundError(path)

    h = hashlib.sha256()
    archivos = [
        p for p in path.rglob("*")
        if p.is_file() and not p.name.endswith(".crc")
    ]
    for archivo in sorted(archivos, key=lambda p: p.relative_to(path).as_posix()):
        rel = archivo.relative_to(path).as_posix().encode("utf-8")
        h.update(len(rel).to_bytes(8, "big"))
        h.update(rel)
        with archivo.open("rb") as f:
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


def _registry_vacio() -> dict:
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "status": "champion",
        "nature": "PoC público independiente; no constituye aprobación ni despliegue CGR",
        "active_serving_profile": None,
        "serving_profiles": {},
    }


def _migrar_registry_v1(data: dict) -> dict:
    if data.get("schema_version") != 1 or data.get("status") != "champion":
        raise ValueError("Registry legacy incompatible.")
    profile = {
        "champion_id": data["champion_id"],
        "promotion": data["promotion"],
        "training": data["training"],
        "models": data["models"],
        "artifacts": data["artifacts"],
    }
    out = _registry_vacio()
    out["active_serving_profile"] = SKLEARN_PROFILE
    out["serving_profiles"][SKLEARN_PROFILE] = profile
    return out


def cargar_registry_unificado(
    path: str | Path = DEFAULT_REGISTRY,
    *,
    allow_missing: bool = False,
) -> dict:
    path = Path(path)
    if not path.exists():
        if allow_missing:
            return _registry_vacio()
        raise FileNotFoundError(
            f"No existe registry champion {path}. TRAIN no habilita serving por sí mismo: "
            "se requiere promoción explícita."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") == 1:
        return _migrar_registry_v1(data)
    if data.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise ValueError(f"Registry con schema_version no soportado: {data.get('schema_version')!r}")
    if data.get("status") != "champion" or not isinstance(data.get("serving_profiles"), dict):
        raise ValueError(f"Registry champion inválido: {path}")
    return data


def _copiar_artefacto(origen: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origen.is_dir():
        if destino.exists():
            shutil.rmtree(destino)
        shutil.copytree(origen, destino, ignore=shutil.ignore_patterns("*.crc"))
    else:
        shutil.copy2(origen, destino)


def _validar_artefactos(artefactos: dict, requeridos: set[str], contexto: str) -> None:
    faltantes = requeridos - set(artefactos)
    if faltantes:
        raise ValueError(f"{contexto} incompleto; faltan artefactos: {sorted(faltantes)}")
    for nombre, spec in artefactos.items():
        ruta = Path(spec["path"])
        if not ruta.exists():
            raise FileNotFoundError(f"Artefacto ausente ({contexto}/{nombre}): {ruta}")
        esperado = spec["sha256"]
        actual = sha256_ruta(ruta)
        if actual != esperado:
            raise ValueError(f"SHA-256 no coincide para {contexto}/{nombre}: {ruta}")


def cargar_manifest_candidato(path: str | Path) -> dict:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        raise ValueError("Manifest candidato incompatible.")
    if data.get("status") != "candidate":
        raise ValueError("El manifest indicado no representa un modelo candidato.")
    _validar_artefactos(data.get("artifacts", {}), SKLEARN_REQUERIDOS, "candidate/sklearn")
    return data


def cargar_manifest_candidato_spark(path: str | Path) -> dict:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != CANDIDATE_SCHEMA_VERSION:
        raise ValueError("Manifest candidato Spark incompatible.")
    if data.get("status") != "candidate" or data.get("engine") != SPARK_PROFILE:
        raise ValueError("El manifest indicado no representa un candidato Spark MLlib.")
    _validar_artefactos(data.get("artifacts", {}), SPARK_REQUERIDOS, "candidate/spark_mllib")
    return data


def _perfil_desde_candidato(candidato: dict, artefactos_champion: dict, approved_by: str) -> dict:
    return {
        "champion_id": candidato["candidate_id"],
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


def promover_candidato(
    manifest_path: str | Path,
    *,
    approved_by: str,
    acknowledge_poc_only: bool,
    registry_path: str | Path = DEFAULT_REGISTRY,
) -> dict:
    if not acknowledge_poc_only:
        raise ValueError(
            "Promoción bloqueada: debe reconocer explícitamente que es solo para el PoC "
            "y no constituye aprobación institucional CGR."
        )
    if not approved_by or not approved_by.strip():
        raise ValueError("approved_by es obligatorio para registrar la promoción del PoC.")

    candidato = cargar_manifest_candidato(manifest_path)
    artefactos_champion = {}
    for nombre, spec in candidato["artifacts"].items():
        if nombre not in SKLEARN_DESTINOS:
            continue
        destino = SKLEARN_DESTINOS[nombre]
        _copiar_artefacto(Path(spec["path"]), destino)
        artefactos_champion[nombre] = {
            "path": destino.as_posix(),
            "sha256": sha256_ruta(destino),
        }

    registry = cargar_registry_unificado(registry_path, allow_missing=True)
    registry["serving_profiles"][SKLEARN_PROFILE] = _perfil_desde_candidato(
        candidato, artefactos_champion, approved_by
    )
    if SPARK_PROFILE not in registry["serving_profiles"]:
        registry["active_serving_profile"] = SKLEARN_PROFILE
    guardar_json_determinista(registry_path, registry)
    return registry["serving_profiles"][SKLEARN_PROFILE]


def promover_candidato_spark(
    manifest_path: str | Path,
    *,
    approved_by: str,
    acknowledge_poc_only: bool,
    registry_path: str | Path = DEFAULT_REGISTRY,
    if_missing: bool = False,
) -> dict:
    if not acknowledge_poc_only:
        raise ValueError(
            "Promoción Spark bloqueada: debe reconocer explícitamente que es solo para el PoC."
        )
    if not approved_by or not approved_by.strip():
        raise ValueError("approved_by es obligatorio para promoción Spark.")

    registry = cargar_registry_unificado(registry_path, allow_missing=True)
    if if_missing and SPARK_PROFILE in registry["serving_profiles"]:
        perfil = cargar_registry_champion(registry_path, profile=SPARK_PROFILE)
        return perfil

    candidato = cargar_manifest_candidato_spark(manifest_path)
    artefactos_champion = {}
    for nombre, spec in candidato["artifacts"].items():
        if nombre not in SPARK_DESTINOS:
            continue
        destino = SPARK_DESTINOS[nombre]
        _copiar_artefacto(Path(spec["path"]), destino)
        artefactos_champion[nombre] = {
            "path": destino.as_posix(),
            "sha256": sha256_ruta(destino),
        }

    registry["serving_profiles"][SPARK_PROFILE] = _perfil_desde_candidato(
        candidato, artefactos_champion, approved_by
    )
    registry["active_serving_profile"] = SPARK_PROFILE
    guardar_json_determinista(registry_path, registry)
    return registry["serving_profiles"][SPARK_PROFILE]


def cargar_registry_champion(
    path: str | Path = DEFAULT_REGISTRY,
    *,
    profile: str | None = None,
) -> dict:
    registry = cargar_registry_unificado(path)
    profile_name = profile or registry.get("active_serving_profile")
    if not profile_name:
        raise ValueError("Registry no tiene serving profile activo.")
    if profile_name not in registry["serving_profiles"]:
        raise ValueError(f"Serving profile no registrado: {profile_name}")

    perfil = registry["serving_profiles"][profile_name]
    if perfil.get("promotion", {}).get("institutional_approval") is not False:
        raise ValueError("El registry PoC no debe declarar aprobación institucional.")
    requeridos = SPARK_REQUERIDOS if profile_name == SPARK_PROFILE else SKLEARN_REQUERIDOS
    _validar_artefactos(perfil.get("artifacts", {}), requeridos, f"champion/{profile_name}")
    out = dict(perfil)
    out["profile_name"] = profile_name
    out["registry_schema_version"] = registry["schema_version"]
    out["active_serving_profile"] = registry.get("active_serving_profile")
    return out
