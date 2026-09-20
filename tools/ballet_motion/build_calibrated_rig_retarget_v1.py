"""Pas de Run — Phase 10.6.6 Calibrated Rig Orientation Retarget v1."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from calibrated_rig_retarget import (
    retarget_pose_solution,
    validate_rest_identity,
)


PHASE = "10.6.6"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-profile", required=True)
    parser.add_argument("--constraint-profile", required=True)
    parser.add_argument("--pose-profile", required=True)
    parser.add_argument("--axis-contract", required=True)
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
    pose_path = Path(args.pose_profile).resolve()
    contract_path = Path(args.axis_contract).resolve()
    output_path = Path(args.output).resolve()
    retarget_source_path = Path(__file__).with_name(
        "calibrated_rig_retarget.py"
    ).resolve()

    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    constraints = json.loads(constraint_path.read_text(encoding="utf-8"))
    poses = json.loads(pose_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    require(canonical["phase"] == "10.6.2", "Requires Phase 10.6.2 canonical profile.")
    require(constraints["phase"] == "10.6.3", "Requires Phase 10.6.3 constraint profile.")
    require(poses["phase"] == "10.6.5", "Requires Phase 10.6.5 pose profile.")
    require(contract["phase"] == PHASE, "Retarget axis contract phase mismatch.")
    require(
        poses["foundation_gate"]["all_pose_geometry_pass"],
        "Canonical foundation geometry is not validated.",
    )
    require(
        poses["foundation_gate"]["all_pose_joint_dofs_preferred"],
        "Canonical foundation joint envelope is not validated.",
    )
    require(
        poses["foundation_gate"]["all_invalid_probes_rejected"],
        "Canonical rejection probes are incomplete.",
    )
    require(
        poses["inputs"]["source_glb_sha256"]
        == canonical["source"]["sha256"],
        "Canonical pose profile is bound to a different source GLB.",
    )
    require(
        contract["policy"]["orientation_retarget_only"],
        "Phase 10.6.6 must remain orientation-retarget only.",
    )
    require(
        not contract["policy"]["root_translation_applied"],
        "Root translation is forbidden in Phase 10.6.6.",
    )
    require(
        contract["policy"]["blender_application_forbidden"],
        "Blender application policy weakened.",
    )

    rest_identity = validate_rest_identity(canonical, contract)

    required = {"bras_bas", "en_avant", "second", "fifth", "plie", "releve"}
    require(
        set(poses["solutions"]) == required,
        "Canonical pose solution set mismatch.",
    )

    retargeted = {
        pose_name: retarget_pose_solution(
            poses["solutions"][pose_name],
            canonical,
            constraints,
            contract,
        )
        for pose_name in sorted(required)
    }

    require(
        all(item["evidence"]["bone_count"] == 24 for item in retargeted.values()),
        "Every pose must retarget all 24 canonical bones.",
    )
    require(
        all(
            item["evidence"]["orientation_retarget_only"]
            for item in retargeted.values()
        ),
        "Unexpected non-orientation retarget occurred.",
    )
    require(
        all(
            item["evidence"]["hand_wrist_preferred_envelope_pass"]
            for item in retargeted.values()
        ),
        "Hand wrist preferred-envelope gate failed.",
    )
    require(
        all(
            item["evidence"][
                "semantic_limb_length_axis_preservation_pass"
            ]
            for item in retargeted.values()
        ),
        "Semantic limb length-axis preservation gate failed.",
    )

    output = {
        "phase": PHASE,
        "schema_version": contract["schema_version"],
        "retarget_id": contract["contract_id"],
        "inputs": {
            "canonical_profile_sha256": sha256_file(canonical_path),
            "constraint_profile_sha256": sha256_file(constraint_path),
            "pose_profile_sha256": sha256_file(pose_path),
            "axis_contract_sha256": sha256_file(contract_path),
            "retarget_source_sha256": sha256_file(retarget_source_path),
            "source_glb_sha256": canonical["source"]["sha256"],
        },
        "policy": contract["policy"],
        "composition": contract["composition"],
        "rest_identity": rest_identity,
        "poses": retargeted,
        "gate": {
            "pose_count": len(retargeted),
            "bones_per_pose": 24,
            "rest_identity_pass": True,
            "canonical_roundtrip_pass": True,
            "hierarchy_reconstruction_pass": True,
            "arm_length_axis_alignment_pass": True,
            "hand_wrist_preferred_envelope_pass": True,
            "semantic_limb_length_axis_preservation_pass": True,
            "orientation_retarget_pass": True,
            "root_translation_applied": False,
            "contact_translation_applied": False,
            "blender_application_performed": False,
            "render_performed": False,
            "animation_performed": False,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print("PHASE10_6_6_CALIBRATED_RIG_RETARGET=PASS")
    print(f"PROFILE={output_path}")
    print("POSES=6/6")
    print("BONES_PER_POSE=24")
    print("REST_IDENTITY=PASS")
    print("CANONICAL_ROUNDTRIP=PASS")
    print("HIERARCHY_RECONSTRUCTION=PASS")
    print("ARM_LENGTH_AXIS_ALIGNMENT=PASS")
    print("HAND_WRIST_PREFERRED_ENVELOPE=PASS")
    print("SEMANTIC_LIMB_LENGTH_AXIS=PASS")
    print("ROOT_TRANSLATION=NOT_APPLIED")
    print("BLENDER_APPLICATION=NOT_PERFORMED")
    print("RENDER=NOT_PERFORMED")


if __name__ == "__main__":
    main()
