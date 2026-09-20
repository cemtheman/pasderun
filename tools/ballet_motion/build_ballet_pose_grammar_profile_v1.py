"""Pas de Run — Phase 10.6.4 Ballet Pose Grammar profile."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ballet_pose_validators import validate_pose


PHASE = "10.6.4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-profile", required=True)
    parser.add_argument("--constraint-profile", required=True)
    parser.add_argument("--grammar", required=True)
    parser.add_argument("--fixtures", required=True)
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
    grammar_path = Path(args.grammar).resolve()
    fixtures_path = Path(args.fixtures).resolve()
    output_path = Path(args.output).resolve()

    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    constraints = json.loads(constraint_path.read_text(encoding="utf-8"))
    grammar = json.loads(grammar_path.read_text(encoding="utf-8"))
    fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))

    require(canonical["phase"] == "10.6.2", "Requires Phase 10.6.2 canonical profile.")
    require(constraints["phase"] == "10.6.3", "Requires Phase 10.6.3 constraint profile.")
    require(grammar["phase"] == PHASE, "Pose grammar phase mismatch.")
    require(
        grammar["coordinate_contract"]["body_front_source"]
        == "DECLARED_BY_RIG_CALIBRATION_ONLY",
        "Pose grammar BODY_FRONT contract weakened.",
    )
    require(
        grammar["coordinate_contract"]["anterior_means"] == "front > 0",
        "Canonical anterior halfspace convention changed.",
    )
    require(
        grammar["policy"]["failed_geometric_validator_blocks_render"],
        "Failed geometry must block render.",
    )
    require(
        grammar["policy"]["failed_geometric_validator_blocks_animation"],
        "Failed geometry must block animation.",
    )

    required_poses = {"bras_bas", "en_avant", "second", "fifth", "plie", "releve"}
    require(
        set(grammar["poses"]) == required_poses,
        f"Pose grammar set mismatch: {sorted(grammar['poses'])}",
    )

    fixture_results = {}
    for name, fixture in fixtures["fixtures"].items():
        pose_name = fixture["pose"]
        require(pose_name in grammar["poses"], f"Unknown fixture pose: {pose_name}")
        result = validate_pose(
            fixture,
            grammar["poses"][pose_name],
            constraints,
            canonical,
        )
        fixture_results[name] = result

        expected = fixture["expected"]
        require(
            result["status"] == expected,
            f"Fixture {name}: expected {expected}, got {result['status']}: {result}",
        )
        if expected == "FAIL" and "expected_failed_validator" in fixture:
            require(
                fixture["expected_failed_validator"] in result["failed_validators"],
                f"Fixture {name}: expected validator "
                f"{fixture['expected_failed_validator']} did not fail.",
            )

    regression = grammar["regression_requirements"]
    require(
        fixture_results["bras_bas_arms_behind_back"]["status"] == "FAIL",
        "Arms-behind-back regression must fail.",
    )
    require(
        "anterior_halfspace"
        in fixture_results["bras_bas_arms_behind_back"]["failed_validators"],
        "Arms-behind-back must fail anterior halfspace.",
    )
    require(
        fixture_results["second_locked_t_pose"]["status"] == "FAIL",
        "Locked T-pose second-position regression must fail.",
    )
    require(
        "wrist_below_shoulder"
        in fixture_results["second_locked_t_pose"]["failed_validators"],
        "Locked T-pose must fail wrist-below-shoulder geometry.",
    )
    for pose_name in regression["independent_foot_yaw_must_fail"]:
        fixture_name = f"{pose_name}_forbidden_foot_yaw"
        require(
            fixture_results[fixture_name]["status"] == "FAIL",
            f"{pose_name}: independent foot yaw regression must fail.",
        )
        require(
            "turnout_chain"
            in fixture_results[fixture_name]["failed_validators"],
            f"{pose_name}: foot yaw must fail turnout_chain.",
        )

    output = {
        "phase": PHASE,
        "schema_version": grammar["schema_version"],
        "profile_id": (
            canonical["profile_id"]
            + "__"
            + constraints["profile_id"]
            + "__"
            + grammar["grammar_id"]
        ),
        "inputs": {
            "canonical_profile_sha256": sha256_file(canonical_path),
            "constraint_profile_sha256": sha256_file(constraint_path),
            "grammar_sha256": sha256_file(grammar_path),
            "fixtures_sha256": sha256_file(fixtures_path),
            "source_glb_sha256": canonical["source"]["sha256"],
        },
        "coordinate_contract": grammar["coordinate_contract"],
        "policy": grammar["policy"],
        "poses": grammar["poses"],
        "regression_requirements": regression,
        "validation": {
            "required_pose_set_complete": True,
            "fixture_results": fixture_results,
            "arms_behind_back_is_blocked": True,
            "locked_t_pose_second_is_blocked": True,
            "independent_foot_yaw_is_blocked": True,
            "render_block_on_geometry_failure": True,
            "animation_block_on_geometry_failure": True,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print("PHASE10_6_4_BALLET_POSE_GRAMMAR=PASS")
    print(f"PROFILE={output_path}")
    print("POSES=bras_bas,en_avant,second,fifth,plie,releve")
    print("ARMS_BEHIND_BACK=BLOCKED")
    print("GEOMETRY_FAIL_BLOCKS_RENDER=TRUE")


if __name__ == "__main__":
    main()
