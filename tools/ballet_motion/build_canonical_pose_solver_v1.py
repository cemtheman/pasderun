"""Pas de Run — Phase 10.6.5 Canonical Pose Solver v1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from canonical_pose_solver import (
    evaluate_rejection_probe,
    solve_pose,
)


PHASE = "10.6.5"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-profile", required=True)
    parser.add_argument("--constraint-profile", required=True)
    parser.add_argument("--grammar-profile", required=True)
    parser.add_argument("--intents", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    args = parse_args()
    canonical_path = Path(args.canonical_profile).resolve()
    constraint_path = Path(args.constraint_profile).resolve()
    grammar_path = Path(args.grammar_profile).resolve()
    intents_path = Path(args.intents).resolve()
    output_path = Path(args.output).resolve()
    solver_source_path = Path(__file__).with_name(
        "canonical_pose_solver.py"
    ).resolve()

    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    constraints = json.loads(constraint_path.read_text(encoding="utf-8"))
    grammar = json.loads(grammar_path.read_text(encoding="utf-8"))
    intents = json.loads(intents_path.read_text(encoding="utf-8"))

    require(canonical["phase"] == "10.6.2", "Requires Phase 10.6.2 canonical profile.")
    require(constraints["phase"] == "10.6.3", "Requires Phase 10.6.3 constraint profile.")
    require(grammar["phase"] == "10.6.4", "Requires Phase 10.6.4 grammar profile.")
    require(intents["phase"] == PHASE, "Pose-solver intent phase mismatch.")
    require(
        grammar["coordinate_contract"]["body_front_source"]
        == "DECLARED_BY_RIG_CALIBRATION_ONLY",
        "BODY_FRONT contract weakened.",
    )
    require(
        grammar["validation"]["arms_behind_back_is_blocked"],
        "10.6.4 arms-behind-back gate missing.",
    )

    required = {"bras_bas", "en_avant", "second", "fifth", "plie", "releve"}
    require(set(intents["poses"]) == required, "Foundation pose intent set mismatch.")
    require(set(grammar["poses"]) == required, "Grammar pose set mismatch.")

    solutions = {
        pose_name: solve_pose(
            pose_name,
            intents,
            grammar,
            canonical,
            constraints,
        )
        for pose_name in sorted(required)
    }

    require(
        all(item["validation"]["status"] == "PASS" for item in solutions.values()),
        "Not all canonical foundation poses passed geometry.",
    )
    require(
        all(
            item["evidence"]["preferred_joint_envelope"] == "PASS"
            for item in solutions.values()
        ),
        "A foundation pose left preferred joint envelope.",
    )

    rejection_probes = {
        name: evaluate_rejection_probe(
            probe,
            intents,
            grammar,
            canonical,
            constraints,
        )
        for name, probe in intents["rejection_probes"].items()
    }
    require(
        all(item["status"] == "REJECTED" for item in rejection_probes.values()),
        f"Invalid pose probe escaped gate: {rejection_probes}",
    )

    output = {
        "phase": PHASE,
        "schema_version": intents["schema_version"],
        "solver_id": intents["solver_id"],
        "inputs": {
            "canonical_profile_sha256": sha256_file(canonical_path),
            "constraint_profile_sha256": sha256_file(constraint_path),
            "grammar_profile_sha256": sha256_file(grammar_path),
            "intent_spec_sha256": sha256_file(intents_path),
            "solver_source_sha256": sha256_file(solver_source_path),
            "source_glb_sha256": canonical["source"]["sha256"],
        },
        "policy": intents["policy"],
        "solutions": solutions,
        "rejection_probes": rejection_probes,
        "foundation_gate": {
            "pose_count": len(solutions),
            "all_pose_geometry_pass": True,
            "all_pose_joint_dofs_preferred": True,
            "all_invalid_probes_rejected": True,
            "rig_retarget_performed": False,
            "render_performed": False,
            "animation_performed": False,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print("PHASE10_6_5_CANONICAL_POSE_SOLVER=PASS")
    print(f"PROFILE={output_path}")
    print("FOUNDATION_POSES=6/6")
    print("PREFERRED_JOINT_ENVELOPE=6/6")
    print("INVALID_PROBES=4/4_REJECTED")
    print("RIG_RETARGET=NOT_PERFORMED")
    print("RENDER=NOT_PERFORMED")


if __name__ == "__main__":
    main()
