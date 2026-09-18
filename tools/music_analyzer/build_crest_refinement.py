#!/usr/bin/env python3
"""Refine an accepted topology-v1 plan with a music-derived CREST fork.

The current 120 s plan remains the rollback baseline. This pass changes only
one already-existing major fork: the strongest rising climax that resolves
directly into RELEASE. Player input, SAFE route, fork timing and merge remain
unchanged; only the upper route silhouette is reshaped.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from build_climax_fork import render_climax_fork_scene
from fork_topology_vocabulary import CREST, classify_topology


TARGET_RANGE_START = 60.0
TARGET_RANGE_END = 90.0
CREST_HEIGHTS = (0.0, 0.28, 0.56, 0.28, 0.0)
ENTRY_LANDING_LENGTH = 1.40
MIN_SEGMENT_LENGTH = 0.40


def _round(value: float) -> float:
    return round(float(value), 4)


def _candidate_score(
    visual_score: dict[str, Any],
    anchor: dict[str, Any],
) -> tuple[float, float, float]:
    window = visual_score["windows"][int(anchor["window_index"])]
    return (
        float(window["metrics"]["climax_peak"]),
        float(window["metrics"]["energy_delta"]),
        float(window["visual_intent"]["lift"]),
    )


def select_crest_anchor(
    visual_score: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    existing_fork_times = {
        float(event["source_time"])
        for event in plan["events"]
        if event.get("branch") is not None
    }
    candidates = [
        anchor
        for anchor in visual_score["event_anchors"]
        if TARGET_RANGE_START <= float(anchor["time"]) < TARGET_RANGE_END
        and float(anchor["time"]) in existing_fork_times
        and classify_topology(visual_score, anchor) == CREST
    ]
    if not candidates:
        raise ValueError("no existing fork qualifies for CREST")
    candidates.sort(
        key=lambda anchor: _candidate_score(visual_score, anchor),
        reverse=True,
    )
    return candidates[0]


def _crest_segments(
    start_x: float,
    end_x: float,
) -> list[dict[str, Any]]:
    length = end_x - start_x
    if length <= ENTRY_LANDING_LENGTH + MIN_SEGMENT_LENGTH * 4:
        raise ValueError("technical runway is too short for CREST")

    remaining = length - ENTRY_LANDING_LENGTH
    tail_count = len(CREST_HEIGHTS) - 1
    tail_length = remaining / tail_count
    if tail_length < MIN_SEGMENT_LENGTH:
        raise ValueError("CREST terrace segments would be too short")

    segments: list[dict[str, Any]] = []
    cursor = start_x
    for index, height in enumerate(CREST_HEIGHTS):
        if index == 0:
            segment_end = cursor + ENTRY_LANDING_LENGTH
        elif index == len(CREST_HEIGHTS) - 1:
            segment_end = end_x
        else:
            segment_end = cursor + tail_length
        segments.append({
            "type": f"CREST_TERRACE_{index + 1:02d}",
            "start_x": _round(cursor),
            "end_x": _round(segment_end),
            "surface_y": _round(height),
            "collision": True,
        })
        cursor = segment_end

    return segments


def build_crest_refinement(
    accepted_plan: dict[str, Any],
    visual_score: dict[str, Any],
) -> dict[str, Any]:
    output = copy.deepcopy(accepted_plan)
    anchor = select_crest_anchor(visual_score, accepted_plan)
    target_time = float(anchor["time"])
    event = next(
        event
        for event in output["events"]
        if abs(float(event["source_time"]) - target_time) <= 1e-6
    )

    branch = event["branch"]
    if branch is None:
        raise ValueError("CREST target must already be a route fork")
    if branch.get("topology") == "CRESCENDO_STAIRCASE":
        raise ValueError("CREST refinement must not replace staircase topology")

    technical = branch["routes"]["technical"]
    collision_segments = [
        segment
        for segment in technical["segments"]
        if bool(segment.get("collision"))
    ]
    if len(collision_segments) != 1:
        raise ValueError("CREST v1 expects one flat technical runway")

    flat = collision_segments[0]
    crest = _crest_segments(
        float(flat["start_x"]),
        float(flat["end_x"]),
    )

    rebuilt: list[dict[str, Any]] = []
    for segment in technical["segments"]:
        if segment is flat:
            rebuilt.extend(crest)
        else:
            rebuilt.append(copy.deepcopy(segment))

    technical["segments"] = rebuilt
    technical["peak_elevation"] = max(float(item["surface_y"]) for item in crest)
    technical["profile"] = "STEPPED_CREST"
    branch["topology"] = CREST
    branch["selection"] = (
        "climax jump reaches a stepped upper CREST; no jump remains on SAFE"
    )
    branch["new_required_actions"] = False
    event["explanation"].append(
        "strong RISE climax followed by RELEASE reshaped the upper route as CREST"
    )
    event["explanation"].append(
        "landing terrace is preserved before the stepped rise-and-fall silhouette"
    )

    output.setdefault("prototype_overlays", {})["fork_topology_v1_1"] = {
        "target_time": _round(target_time),
        "topology": CREST,
        "profile": "STEPPED_CREST",
        "heights": list(CREST_HEIGHTS),
        "entry_landing_length": ENTRY_LANDING_LENGTH,
        "new_required_actions": False,
        "safe_route_changed": False,
        "fork_timing_changed": False,
        "merge_changed": False,
    }
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accepted_plan", type=Path)
    parser.add_argument("visual_score", type=Path)
    parser.add_argument("--plan-output", required=True, type=Path)
    parser.add_argument("--scene-output", required=True, type=Path)
    args = parser.parse_args()

    accepted_plan = json.loads(args.accepted_plan.read_text(encoding="utf-8"))
    visual_score = json.loads(args.visual_score.read_text(encoding="utf-8"))
    output = build_crest_refinement(accepted_plan, visual_score)
    scene = render_climax_fork_scene(output)

    args.plan_output.parent.mkdir(parents=True, exist_ok=True)
    args.scene_output.parent.mkdir(parents=True, exist_ok=True)
    args.plan_output.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    args.scene_output.write_text(scene, encoding="utf-8")


if __name__ == "__main__":
    main()
