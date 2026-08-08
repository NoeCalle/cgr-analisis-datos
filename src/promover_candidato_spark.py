"""Promoción explícita del candidate Spark MLlib al registry unificado."""

from __future__ import annotations

import argparse

from registro_modelos import DEFAULT_REGISTRY, promover_candidato_spark


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Promueve un candidate Spark MLlib al champion técnico del PoC. "
            "No representa aprobación institucional CGR."
        )
    )
    parser.add_argument(
        "--manifest",
        default="outputs/runtime/spark_model_candidates/candidate_manifest.json",
    )
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--acknowledge-poc-only", action="store_true")
    parser.add_argument(
        "--if-missing",
        action="store_true",
        help=(
            "Bootstrap reproducible: si ya existe un champion Spark válido, no lo reemplaza "
            "por el candidate de la corrida actual."
        ),
    )
    args = parser.parse_args()

    perfil = promover_candidato_spark(
        args.manifest,
        approved_by=args.approved_by,
        acknowledge_poc_only=args.acknowledge_poc_only,
        registry_path=args.registry,
        if_missing=args.if_missing,
    )
    print(f"Champion Spark PoC: {perfil['champion_id']}")
    print(f"Registry: {args.registry}")
    print("active_serving_profile=spark_mllib")
    print("institutional_approval=false")


if __name__ == "__main__":
    main()
