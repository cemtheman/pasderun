"""Solve every integer frame between explicitly authored arm target endpoints."""

from __future__ import annotations

import json
from pathlib import Path

from schema_validation import require, shape
from static_pose import solve_static_pose, validate_target_spec


SCHEMA = json.loads(Path(__file__).with_name("arm_transition_v0_5.schema.json").read_text(encoding="utf-8"))


def solve_arm_transition(spec, calibration):
    shape(spec, SCHEMA, "transition", {})
    first = validate_target_spec(spec["start_pose"], calibration)
    last = validate_target_spec(spec["end_pose"], calibration)
    before = {t["side"]: t for t in first["targets"]}
    after = {t["side"]: t for t in last["targets"]}
    require(before.keys() == after.keys(), "transition", "arm sides differ between endpoints")
    for side in before:
        require(before[side]["bend_plane"] == after[side]["bend_plane"],
                "transition", f"{side}: bend plane changes; explicit pole transition required")
    frames = []
    count = spec["duration_frames"]
    for index in range(count):
        t = index / (count - 1)
        weight = t*t*(3 - 2*t)
        targets = []
        for side, a in before.items():
            b = after[side]
            targets.append({"side": side, "landmark": a["landmark"],
                            "bend_plane": a["bend_plane"],
                            "reach_fraction": a["reach_fraction"] + weight*(b["reach_fraction"]-a["reach_fraction"]),
                            "offset_body_arm_reach": [x + weight*(y-x) for x, y in zip(a["offset_body_arm_reach"], b["offset_body_arm_reach"])]})
        pose = {"schema_version": "0.3.0", "pose_id": spec["transition_id"],
                "rig_profile_id": first["rig_profile_id"], "targets": targets}
        solution = solve_static_pose(pose, calibration)
        frames.append({"frame": index + 1, "arms": solution["arms"]})
    return {"schema_version": "0.5.1", "transition_id": spec["transition_id"],
            "source_glb_sha256": calibration["source"]["sha256"],
            "fps": spec["fps"], "duration_frames": count, "frames": frames,
            "limits": "Arm geometry probe only; no contact, balance or ballet technique approval"}
