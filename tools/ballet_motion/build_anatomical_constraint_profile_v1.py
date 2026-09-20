"""Pas de Run — Phase 10.6.3 Anatomical Constraint Profile."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from anatomical_constraints import (
    knee_external_rotation_cap_deg,
    validate_limit_table,
    validate_turnout_request,
)


PHASE = "10.6.3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-profile", required=True)
    parser.add_argument("--canonical-spec", required=True)
    parser.add_argument("--constraints", required=True)
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
    canonical_profile_path = Path(args.canonical_profile).resolve()
    canonical_spec_path = Path(args.canonical_spec).resolve()
    constraints_path = Path(args.constraints).resolve()
    output_path = Path(args.output).resolve()

    canonical_profile = json.loads(
        canonical_profile_path.read_text(encoding="utf-8")
    )
    canonical_spec = json.loads(
        canonical_spec_path.read_text(encoding="utf-8")
    )
    constraints = json.loads(
        constraints_path.read_text(encoding="utf-8")
    )

    require(
        canonical_profile["phase"] == "10.6.2",
        "Requires Phase 10.6.2 canonical profile.",
    )
    require(
        constraints["phase"] == PHASE,
        "Constraint source phase mismatch.",
    )
    require(
        canonical_profile["body_frame"]["front_policy"]
        == "DECLARED_BY_RIG_CALIBRATION_ONLY",
        "BODY_FRONT contract was weakened.",
    )

    table_errors = validate_limit_table(canonical_spec, constraints)
    require(
        not table_errors,
        "Anatomical limit table invalid: " + "; ".join(table_errors),
    )

    turnout = constraints["turnout_model"]
    require(
        turnout["primary_authority"]
        == "hip_ball.internal_external_rotation",
        "Hip must remain primary turnout authority.",
    )
    require(
        not turnout["knee_axial_coupling"]["independent_solver_dof"],
        "Knee axial rotation may only be a coupled derived contribution.",
    )
    require(
        turnout["ankle_foot"]["turnout_generation_by_foot_yaw_forbidden"],
        "Independent foot yaw must not generate turnout.",
    )

    bone_constraints = {}
    for bone_name, bone in canonical_profile["canonical_bones"].items():
        joint_class = bone["joint_class"]
        bone_constraints[bone_name] = {
            "joint_class": joint_class,
            "limits": constraints["joint_limits"][joint_class],
        }

    turnout_validation_examples = {
        "neutral_first_position_like": validate_turnout_request(
            constraints,
            hip_external_rotation_deg=35.0,
            knee_external_rotation_deg=4.0,
            knee_flexion_deg=10.0,
            independent_foot_yaw_deg=0.0,
        ),
        "demi_plie_like": validate_turnout_request(
            constraints,
            hip_external_rotation_deg=45.0,
            knee_external_rotation_deg=8.0,
            knee_flexion_deg=45.0,
            independent_foot_yaw_deg=0.0,
        ),
        "forbidden_foot_twist": validate_turnout_request(
            constraints,
            hip_external_rotation_deg=35.0,
            knee_external_rotation_deg=4.0,
            knee_flexion_deg=10.0,
            independent_foot_yaw_deg=10.0,
        ),
    }

    require(
        turnout_validation_examples["neutral_first_position_like"]["status"]
        == "PASS",
        "Neutral turnout example must pass.",
    )
    require(
        turnout_validation_examples["demi_plie_like"]["status"]
        == "PASS",
        "Demi-plie turnout example must pass.",
    )
    require(
        turnout_validation_examples["forbidden_foot_twist"]["status"]
        == "HARD_LIMIT",
        "Independent foot yaw example must fail.",
    )

    output = {
        "phase": PHASE,
        "schema_version": constraints["schema_version"],
        "profile_id": (
            canonical_profile["profile_id"]
            + "__"
            + constraints["profile_id"]
        ),
        "inputs": {
            "canonical_profile_sha256": sha256_file(
                canonical_profile_path
            ),
            "canonical_spec_sha256": sha256_file(canonical_spec_path),
            "constraint_spec_sha256": sha256_file(constraints_path),
            "source_glb_sha256": canonical_profile["source"]["sha256"],
        },
        "body_frame": canonical_profile["body_frame"],
        "policy": constraints["policy"],
        "conventions": constraints["conventions"],
        "joint_limits": constraints["joint_limits"],
        "bone_constraints": bone_constraints,
        "turnout_model": turnout,
        "coupling_constraints": constraints["coupling_constraints"],
        "validation": {
            "limit_table_valid": True,
            "all_canonical_rotational_dofs_covered": True,
            "no_undeclared_joint_dof_authority": True,
            "hip_is_primary_turnout_authority": True,
            "knee_axial_rotation_is_derived_only": True,
            "independent_foot_yaw_forbidden": True,
            "knee_external_rotation_caps_deg": {
                "extension": round(
                    knee_external_rotation_cap_deg(constraints, 0.0), 8
                ),
                "45_flexion": round(
                    knee_external_rotation_cap_deg(constraints, 45.0), 8
                ),
                "90_flexion": round(
                    knee_external_rotation_cap_deg(constraints, 90.0), 8
                ),
            },
            "turnout_examples": turnout_validation_examples,
        },
        "sources": constraints["sources"],
        "notes": constraints["notes"],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8",
    )

    print("PHASE10_6_3_ANATOMICAL_CONSTRAINTS=PASS")
    print(f"PROFILE={output_path}")
    print(f"BONES={len(bone_constraints)}")
    print("TURNOUT_PRIMARY=HIP")
    print("KNEE_AXIAL=DERIVED_ONLY")
    print("FOOT_YAW=FORBIDDEN")


if __name__ == "__main__":
    main()
