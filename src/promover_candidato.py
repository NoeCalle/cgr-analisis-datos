"""Promoción explícita de un candidato al champion usado por INFERENCE del PoC."""

from __future__ import annotations

import argparse

from registro_modelos import DEFAULT_REGISTRY, promover_candidato


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Promueve un manifest candidate al registry champion del PoC. "
            "No representa aprobación institucional CGR."
        )
    )
    parser.add_argument(
        "--manifest",
        default="outputs/runtime/model_candidates/candidate_manifest.json",
    )
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--approved-by", required=True)
    parser.add_argument(
        "--acknowledge-poc-only",
        action="store_true",
        help="Reconoce que la promoción es solo técnica del PoC y no institucional.",
    )
    args = parser.parse_args()

    registry = promover_candidato(
        args.manifest,
        approved_by=args.approved_by,
        acknowledge_poc_only=args.acknowledge_poc_only,
        registry_path=args.registry,
    )
    print(f"Champion PoC: {registry['champion_id']}")
    print(f"Registry: {args.registry}")
    print("institutional_approval=false")


if __name__ == "__main__":
    main()
