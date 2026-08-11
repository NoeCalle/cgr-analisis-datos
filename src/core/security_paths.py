"""Guardrails de filesystem para TRAIN y promoción de candidates.

Los trainers del PoC solo pueden limpiar directorios bajo roots explícitamente
autorizados. Los manifests candidatos solo pueden referenciar artefactos que
resuelvan dentro del mismo directorio del manifest, incluyendo symlinks.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Mapping

DEFAULT_ALLOWED_CANDIDATE_ROOT = Path("outputs/runtime")
ALLOWED_ROOTS_ENV = "CGR_ALLOWED_CANDIDATE_ROOTS"
EXPECTED_MANIFEST_NAME = "candidate_manifest.json"


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def allowed_candidate_roots() -> tuple[Path, ...]:
    """Roots autorizados; se puede ampliar en CGR vía variable de entorno.

    ``CGR_ALLOWED_CANDIDATE_ROOTS`` usa ``os.pathsep`` para admitir varios roots.
    Si no se define, solo ``outputs/runtime`` puede ser limpiado por TRAIN.
    """
    raw = os.environ.get(ALLOWED_ROOTS_ENV, "").strip()
    values = [v.strip() for v in raw.split(os.pathsep) if v.strip()] if raw else []
    if not values:
        values = [str(DEFAULT_ALLOWED_CANDIDATE_ROOT)]
    return tuple(Path(value).expanduser().resolve(strict=False) for value in values)


def preparar_directorio_candidato(manifest_path: str | Path) -> tuple[Path, Path]:
    """Valida y prepara el directorio de un candidate sin borrar fuera del runtime.

    El nombre del manifest es fijo y su directorio padre debe estar estrictamente
    debajo de uno de los roots autorizados. Un root nunca puede borrarse completo.
    """
    manifest = Path(manifest_path)
    if manifest.name != EXPECTED_MANIFEST_NAME:
        raise ValueError(
            f"Manifest candidate inseguro: se requiere nombre {EXPECTED_MANIFEST_NAME!r}, "
            f"recibido {manifest.name!r}."
        )

    candidate_dir = manifest.parent
    candidate_resolved = candidate_dir.expanduser().resolve(strict=False)
    roots = allowed_candidate_roots()
    if not any(
        candidate_resolved != root and _is_within(candidate_resolved, root)
        for root in roots
    ):
        raise ValueError(
            "Directorio candidate fuera de roots autorizados: "
            f"{candidate_resolved}. Configure {ALLOWED_ROOTS_ENV} para un runtime institucional."
        )

    if candidate_dir.is_symlink():
        raise ValueError(f"Directorio candidate no puede ser symlink: {candidate_dir}")
    if candidate_dir.exists():
        shutil.rmtree(candidate_dir)
    candidate_dir.mkdir(parents=True, exist_ok=False)
    return manifest, candidate_dir


def validar_artefactos_dentro_del_candidate(
    manifest_path: str | Path,
    artefactos: Mapping[str, Mapping[str, object]],
) -> None:
    """Bloquea manifests que apunten fuera de su propio directorio candidate.

    ``Path.resolve(strict=True)`` también resuelve symlinks, por lo que un enlace
    aparente dentro del candidate que apunte fuera queda rechazado.
    """
    root = Path(manifest_path).parent.expanduser().resolve(strict=True)
    for nombre, spec in artefactos.items():
        raw_path = spec.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError(f"Artefacto candidate {nombre!r} no define path válido.")
        resolved = Path(raw_path).expanduser().resolve(strict=True)
        if not _is_within(resolved, root):
            raise ValueError(
                f"Artefacto candidate fuera de su directorio: {nombre} -> {resolved}; root={root}"
            )
