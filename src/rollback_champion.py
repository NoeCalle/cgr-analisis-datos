"""Rollback explícito de un champion técnico previamente registrado.

No crea, entrena ni retunea modelos. Solo cambia el puntero del registry hacia
un champion histórico cuyos artefactos siguen presentes y verifican SHA-256.
No representa aprobación ni rollback institucional CGR.
"""

from __future__ import annotations

import argparse

from registro_modelos import (
    DEFAULT_REGISTRY,
    SKLEARN_PROFILE,
    SPARK_PROFILE,
    rollback_champion,
)


def main():
    parser = argparse.ArgumentParser(
        description="Revierte explícitamente el registry PoC a un champion histórico verificable."
    )
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--profile", choices=[SKLEARN_PROFILE, SPARK_PROFILE], default=SPARK_PROFILE)
    parser.add_argument("--champion-id", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--acknowledge-poc-only", action="store_true")
    args = parser.parse_args()

    perfil = rollback_champion(
        profile=args.profile,
        champion_id=args.champion_id,
        approved_by=args.approved_by,
        acknowledge_poc_only=args.acknowledge_poc_only,
        registry_path=args.registry,
    )
    print(f"Rollback PoC completado: profile={args.profile} champion={perfil['champion_id']}")
    print("institutional_approval=false")


if __name__ == "__main__":
    main()
