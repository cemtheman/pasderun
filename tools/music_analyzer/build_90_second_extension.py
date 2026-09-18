#!/usr/bin/env python3
"""Extend the accepted Phase 9 0–60 baseline to 90 seconds.

The accepted 0–60 derived plan is treated as immutable gameplay evidence.
Only x >= 240 (60 seconds at 4 u/s) is derived from the 90-second compiler,
new passive Spatial Score, and major-climax fork rules.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from build_climax_fork import (
    MAJOR_CLIMAX_MINIMUM,
    _apply_climax_fork,
    render_climax_fork_scene,
)
from build_spatial_score import build_spatial_score
from compile_geometry import RUN_SPEED, compile_plan
from render_spatial_geometry import apply_spatial_score


BASELINE_END_SECONDS = 60.0
EXTENSION_END_SECONDS = 90.0
BASELINE_END_X = BASELINE_END_SECONDS * RUN_SPEED
MIN_INTERVAL_LENGTH = 0.0001


def _round(value: float) -> float:
    return round(float(value), 4)


def _clip_prefix_runways(
    intervals: list[dict[str, Any]],
    boundary_x: float,
) -> list[dict[str, float]]:
    output: list[dict[str, float]] = []
    for interval in intervals:
        left = float(interval["start_x"])
        right = min(float(interval["end_x"]), boundary_x)
        if right - left < MIN_INTERVAL_LENGTH or left >= boundary_x:
            continue
        output.append({
            "start_x": _round(left),
            "end_x": _round(right),
            "surface_y": _round(interval["surface_y"]),
        })
    return output


def _clip_extension_runways(
    intervals: list[dict[str, Any]],
    boundary_x: float,
) -> list[dict[str, float]]:
    output: list[dict[str, float]] = []
    for interval in intervals:
        left = max(float(interval["start_x"]), boundary_x)
        right = float(interval["end_x"])
        if right - left < MIN_INTERVAL_LENGTH or right <= boundary_x:
            continue
        output.append({
            "start_x": _round(left),
            "end_x": _round(right),
            "surface_y": _round(interval["surface_y"]),
        })
    return output


def _major_extension_climaxes(
    visual_score: dict[str, Any],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    windows = visual_score["windows"]
    candidates: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for anchor in visual_score["event_anchors"]:
        time = float(anchor["time"])
        if not (BASELINE_END_SECONDS <= time < EXTENSION_END_SECONDS):
            continue
        interaction = anchor["interaction"]
        if not bool(interaction["required"]):
            continue
        if interaction["candidate_action"] != "JUMP":
            continue
        window = windows[int(anchor["window_index"])]
        if window["visual_intent"]["phrase_role"] != "CLIMAX":
            continue
        if float(window["metrics"]["climax_peak"]) < MAJOR_CLIMAX_MINIMUM:
            continue
        candidates.append((time, anchor, window))

    candidates.sort(key=lambda item: item[0])
    return [(anchor, window) for _, anchor, window in candidates]


def build_90_second_extension(
    movement_demands: dict[str, Any],
    visual_score: dict[str, Any],
    accepted_60_plan: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if float(accepted_60_plan["compiled_time_range"]["end"]) != BASELINE_END_SECONDS:
        raise ValueError("accepted baseline must end at exactly 60 seconds")

    base_90 = compile_plan(movement_demands, EXTENSION_END_SECONDS)
    spatial_60_90 = build_spatial_score(
        visual_score,
        base_90,
        start_seconds=BASELINE_END_SECONDS,
        end_seconds=EXTENSION_END_SECONDS,
    )
    spatialized_90 = apply_spatial_score(base_90, spatial_60_90)

    accepted_events = [
        copy.deepcopy(event)
        for event in accepted_60_plan["events"]
        if float(event["source_time"]) <= BASELINE_END_SECONDS
    ]
    extension_events = [
        copy.deepcopy(event)
        for event in spatialized_90["events"]
        if float(event["source_time"]) > BASELINE_END_SECONDS
    ]

    output = copy.deepcopy(spatialized_90)
    output["events"] = accepted_events + extension_events
    output["surface_plan"]["runway_intervals"] = sorted(
        _clip_prefix_runways(
            accepted_60_plan["surface_plan"]["runway_intervals"],
            BASELINE_END_X,
        )
        + _clip_extension_runways(
            spatialized_90["surface_plan"]["runway_intervals"],
            BASELINE_END_X,
        ),
        key=lambda item: (item["start_x"], item["end_x"]),
    )
    output["surface_plan"]["balance_intervals"] = copy.deepcopy(
        accepted_60_plan["surface_plan"].get("balance_intervals", [])
    )
    output["surface_plan"]["ramps"] = copy.deepcopy(
        accepted_60_plan["surface_plan"].get("ramps", [])
    )

    accepted_overlays = copy.deepcopy(
        accepted_60_plan.get("prototype_overlays", {}).get("climax_forks_v0_2", [])
    )
    extension_overlays: list[dict[str, Any]] = []
    minimum_approach_x = BASELINE_END_X
    for anchor, climax_window in _major_extension_climaxes(visual_score):
        overlay = _apply_climax_fork(
            output,
            visual_score,
            anchor,
            climax_window,
            minimum_approach_x,
        )
        extension_overlays.append(overlay)
        minimum_approach_x = float(overlay["merge_x"])

    output["source_spatial_scores"] = [
        "data/geometry/graceful_opening_30_60.spatial_score_v0_1.json",
        "data/geometry/graceful_opening_60_90.spatial_score_v0_1.json",
    ]
    output["source_visual_score"] = "data/music/graceful_opening.visual_score_v0_1.json"
    output["prototype_overlays"] = copy.deepcopy(
        accepted_60_plan.get("prototype_overlays", {})
    )
    output["prototype_overlays"]["climax_forks_v0_3"] = (
        accepted_overlays + extension_overlays
    )
    output["prototype_overlays"]["extension_60_90"] = {
        "baseline_end_seconds": BASELINE_END_SECONDS,
        "baseline_end_x": BASELINE_END_X,
        "baseline_immutable": True,
        "major_climax_threshold": MAJOR_CLIMAX_MINIMUM,
        "fork_times": [item["target_time"] for item in extension_overlays],
        "new_required_actions": False,
    }

    return base_90, spatial_60_90, output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("movement_demands", type=Path)
    parser.add_argument("visual_score", type=Path)
    parser.add_argument("accepted_60_plan", type=Path)
    parser.add_argument("--base-plan-output", required=True, type=Path)
    parser.add_argument("--spatial-output", required=True, type=Path)
    parser.add_argument("--plan-output", required=True, type=Path)
    parser.add_argument("--scene-output", required=True, type=Path)
    args = parser.parse_args()

    movement_demands = json.loads(args.movement_demands.read_text(encoding="utf-8"))
    visual_score = json.loads(args.visual_score.read_text(encoding="utf-8"))
    accepted_60_plan = json.loads(args.accepted_60_plan.read_text(encoding="utf-8"))

    base_90, spatial_60_90, plan_90 = build_90_second_extension(
        movement_demands,
        visual_score,
        accepted_60_plan,
    )
    scene_90 = render_climax_fork_scene(plan_90)

    outputs = (
        (args.base_plan_output, base_90),
        (args.spatial_output, spatial_60_90),
        (args.plan_output, plan_90),
    )
    for path, payload in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )

    args.scene_output.parent.mkdir(parents=True, exist_ok=True)
    args.scene_output.write_text(scene_90, encoding="utf-8")


if __name__ == "__main__":
    main()
