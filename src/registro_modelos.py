"""Registry técnico unificado para TRAIN, promoción e INFERENCE.

El PoC mantiene dos perfiles diferenciados dentro de un único registry:
- ``sklearn``: benchmark/serving de compatibilidad;
- ``spark_mllib``: serving objetivo alineado a la arquitectura del TDR.

La promoción siempre es explícita y nunca implica aprobación institucional CGR.
Los artefactos pueden ser archivos o directorios Spark y se verifican por SHA-256.
Desde 3B, las nuevas promociones se almacenan de forma inmutable por candidate_id;
el registry cambia su puntero solo después de copiar/verificar el conjunto completo y
conserva historial suficiente para rollback explícito. Los registries/champions
legacy continúan siendo legibles sin migración forzada.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

CANDIDATE_SCHEMA_VERSION = 2
SUPPORTED_CANDIDATE_SCHEMA_VERSIONS = {1, 2}
REGISTRY_SCHEMA_VERSION = 2
DEFAULT_REGISTRY = Path("outputs/model_registry.json")
CHAMPION_STORE_ROOT = Path("outputs/champion_store")

SKLEARN_PROFILE = "sklearn"
SPARK_PROFILE = "spark_mllib"

# Rutas legacy: se conservan únicamente para leer champions ya versionados en
# el repositorio. Las promociones nuevas NO vuelven a sobrescribirlas.
SKLEARN_CHAMPION_DIR = Path("outputs/champions")
SPARK_CHAMPION_DIR = Path("outputs/champions_spark")

SKLEARN_DESTINOS = {
    "preprocessor": "preprocesador_contratos.joblib",
    "preprocessor_json": "preprocesador_contratos.json",
    "favoritismo_model": "modelo_favoritismo_rf.joblib",
    "fraccionamiento_model": "modelo_fraccionamiento_isoforest.joblib",
    "fraccionamiento_scaler": "scaler_fraccionamiento.joblib",
}
SKLEARN_REQUERIDOS = {
    "preprocessor",
    "favoritismo_model",
    "fraccionamiento_model",
    "fraccionamiento_scaler",
}

SPARK_DESTINOS = {
    "preprocessor_json": "preprocesador_contratos.json",
    "preprocessor_medians": "medianas_monto_por_objeto",
    "favoritismo_model": "modelo_favoritismo_rf",
    "fraccionamiento_model": "modelo_fraccionamiento_kmeans",
    "fraccionamiento_scaler": "scaler_fraccionamiento",
}
# Las medianas externas son opcionales para conservar compatibilidad con
# champions entrenados desde CSV/SQL Server, cuyo mapa vive dentro del JSON.
SPARK_REQUERIDOS = {
    "preprocessor_json",
    "favoritismo_model",
    "fraccionamiento_model",
    "fraccionamiento_scaler",
}

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


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
    """Escribe JSON de forma determinista y reemplaza el archivo atómicamente."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _registry_vacio() -> dict:
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "status": "champion",
        "nature": "PoC público independiente; no constituye aprobación ni despliegue CGR",
        "active_serving_profile": None,
        "serving_profiles": {},
        "history": {},
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
    data.setdefault("history", {})
    return data


def _copiar_artefacto(origen: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origen.is_dir():
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


def _validar_schema_candidate(data: dict, contexto: str) -> int:
    version = data.get("schema_version")
    if version not in SUPPORTED_CANDIDATE_SCHEMA_VERSIONS:
        raise ValueError(f"Manifest candidato {contexto} incompatible: schema_version={version!r}")
    return int(version)


def cargar_manifest_candidato(path: str | Path) -> dict:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    _validar_schema_candidate(data, "sklearn")
    if data.get("status") != "candidate":
        raise ValueError("El manifest indicado no representa un modelo candidato.")
    _validar_artefactos(data.get("artifacts", {}), SKLEARN_REQUERIDOS, "candidate/sklearn")
    return data


def cargar_manifest_candidato_spark(path: str | Path) -> dict:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    version = _validar_schema_candidate(data, "Spark")
    if data.get("status") != "candidate" or data.get("engine") != SPARK_PROFILE:
        raise ValueError("El manifest indicado no representa un candidato Spark MLlib.")
    if version >= 2 and data.get("training", {}).get("validation_state") != "evaluated_same_corpus":
        raise ValueError(
            "Candidate Spark pendiente de evaluación sobre su propio corpus; promoción bloqueada."
        )
    _validar_artefactos(data.get("artifacts", {}), SPARK_REQUERIDOS, "candidate/spark_mllib")
    return data


def _validar_candidate_id(candidate_id: str) -> str:
    if not isinstance(candidate_id, str) or not _SAFE_ID.fullmatch(candidate_id):
        raise ValueError(f"candidate_id no seguro para almacenamiento: {candidate_id!r}")
    return candidate_id


def _destinos_versionados(
    profile: str,
    candidate_id: str,
    *,
    store_root: str | Path = CHAMPION_STORE_ROOT,
) -> tuple[Path, dict[str, Path]]:
    candidate_id = _validar_candidate_id(candidate_id)
    if profile == SPARK_PROFILE:
        nombres = SPARK_DESTINOS
    elif profile == SKLEARN_PROFILE:
        nombres = SKLEARN_DESTINOS
    else:
        raise ValueError(f"Perfil de serving no soportado: {profile}")
    final_root = Path(store_root) / profile / candidate_id
    return final_root, {nombre: final_root / rel for nombre, rel in nombres.items()}


def _materializar_champion_inmutable(
    candidato: dict,
    *,
    profile: str,
    store_root: str | Path = CHAMPION_STORE_ROOT,
) -> dict:
    """Copia el conjunto completo a staging y publica el directorio de una vez."""
    final_root, destinos = _destinos_versionados(
        profile, candidato["candidate_id"], store_root=store_root
    )
    requeridos = SPARK_REQUERIDOS if profile == SPARK_PROFILE else SKLEARN_REQUERIDOS

    if final_root.exists():
        existentes = {
            nombre: {"path": destino.as_posix(), "sha256": spec["sha256"]}
            for nombre, spec in candidato["artifacts"].items()
            if nombre in destinos
            for destino in [destinos[nombre]]
        }
        _validar_artefactos(existentes, requeridos, f"immutable/{profile}")
        return existentes

    final_root.parent.mkdir(parents=True, exist_ok=True)
    staging = final_root.parent / f".{final_root.name}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=False, exist_ok=False)
    try:
        staged_specs: dict[str, dict] = {}
        for nombre, spec in candidato["artifacts"].items():
            if nombre not in destinos:
                continue
            rel = destinos[nombre].relative_to(final_root)
            destino_staging = staging / rel
            _copiar_artefacto(Path(spec["path"]), destino_staging)
            actual = sha256_ruta(destino_staging)
            if actual != spec["sha256"]:
                raise ValueError(
                    f"Copia de champion alteró {profile}/{nombre}: "
                    f"esperado={spec['sha256']} actual={actual}"
                )
            staged_specs[nombre] = {
                "path": (final_root / rel).as_posix(),
                "sha256": actual,
            }
        if requeridos - set(staged_specs):
            raise ValueError(
                f"Champion {profile} incompleto antes de publicar: "
                f"{sorted(requeridos - set(staged_specs))}"
            )
        staging.rename(final_root)
        _validar_artefactos(staged_specs, requeridos, f"immutable/{profile}")
        return staged_specs
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def _registrar_champion_anterior(registry: dict, profile: str) -> None:
    actual = registry.get("serving_profiles", {}).get(profile)
    if not actual:
        return
    history = registry.setdefault("history", {}).setdefault(profile, [])
    champion_id = actual.get("champion_id")
    if champion_id and not any(h.get("champion_id") == champion_id for h in history):
        history.append(deepcopy(actual))


def _perfil_desde_candidato(candidato: dict, artefactos_champion: dict, approved_by: str) -> dict:
    return {
        "champion_id": candidato["candidate_id"],
        "promotion": {
            "trigger": "explicit_command",
            "approved_by": approved_by.strip(),
            "scope": "poc_technical_serving",
            "institutional_approval": False,
            "artifact_storage": "immutable_versioned",
            "candidate_schema_version": candidato.get("schema_version"),
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
    store_root: str | Path = CHAMPION_STORE_ROOT,
) -> dict:
    if not acknowledge_poc_only:
        raise ValueError(
            "Promoción bloqueada: debe reconocer explícitamente que es solo para el PoC "
            "y no constituye aprobación institucional CGR."
        )
    if not approved_by or not approved_by.strip():
        raise ValueError("approved_by es obligatorio para registrar la promoción del PoC.")

    candidato = cargar_manifest_candidato(manifest_path)
    artefactos_champion = _materializar_champion_inmutable(
        candidato, profile=SKLEARN_PROFILE, store_root=store_root
    )

    registry = cargar_registry_unificado(registry_path, allow_missing=True)
    _registrar_champion_anterior(registry, SKLEARN_PROFILE)
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
    store_root: str | Path = CHAMPION_STORE_ROOT,
) -> dict:
    if not acknowledge_poc_only:
        raise ValueError(
            "Promoción Spark bloqueada: debe reconocer explícitamente que es solo para el PoC."
        )
    if not approved_by or not approved_by.strip():
        raise ValueError("approved_by es obligatorio para promoción Spark.")

    registry = cargar_registry_unificado(registry_path, allow_missing=True)
    if if_missing and SPARK_PROFILE in registry["serving_profiles"]:
        return cargar_registry_champion(registry_path, profile=SPARK_PROFILE)

    candidato = cargar_manifest_candidato_spark(manifest_path)
    artefactos_champion = _materializar_champion_inmutable(
        candidato, profile=SPARK_PROFILE, store_root=store_root
    )

    _registrar_champion_anterior(registry, SPARK_PROFILE)
    registry["serving_profiles"][SPARK_PROFILE] = _perfil_desde_candidato(
        candidato, artefactos_champion, approved_by
    )
    registry["active_serving_profile"] = SPARK_PROFILE
    guardar_json_determinista(registry_path, registry)
    return registry["serving_profiles"][SPARK_PROFILE]


def rollback_champion(
    *,
    profile: str,
    champion_id: str,
    approved_by: str,
    acknowledge_poc_only: bool,
    registry_path: str | Path = DEFAULT_REGISTRY,
) -> dict:
    """Revierte explícitamente el puntero a un champion histórico verificable."""
    if not acknowledge_poc_only:
        raise ValueError("Rollback bloqueado: debe reconocer explícitamente el alcance PoC.")
    if not approved_by or not approved_by.strip():
        raise ValueError("approved_by es obligatorio para rollback.")
    if profile not in {SKLEARN_PROFILE, SPARK_PROFILE}:
        raise ValueError(f"Perfil de serving no soportado: {profile}")

    registry = cargar_registry_unificado(registry_path)
    actual = registry.get("serving_profiles", {}).get(profile)
    if not actual:
        raise ValueError(f"No existe champion actual para {profile}.")
    if actual.get("champion_id") == champion_id:
        return cargar_registry_champion(registry_path, profile=profile)

    history = registry.get("history", {}).get(profile, [])
    target = next((deepcopy(h) for h in history if h.get("champion_id") == champion_id), None)
    if target is None:
        raise ValueError(f"Champion histórico no encontrado para rollback: {profile}/{champion_id}")

    requeridos = SPARK_REQUERIDOS if profile == SPARK_PROFILE else SKLEARN_REQUERIDOS
    _validar_artefactos(target.get("artifacts", {}), requeridos, f"rollback/{profile}")
    _registrar_champion_anterior(registry, profile)

    original_promotion = deepcopy(target.get("promotion", {}))
    target["promotion"] = {
        "trigger": "explicit_rollback",
        "approved_by": approved_by.strip(),
        "scope": "poc_technical_serving",
        "institutional_approval": False,
        "rolled_back_from": actual.get("champion_id"),
        "original_promotion": original_promotion,
    }
    registry["serving_profiles"][profile] = target
    guardar_json_determinista(registry_path, registry)
    return cargar_registry_champion(registry_path, profile=profile)


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
