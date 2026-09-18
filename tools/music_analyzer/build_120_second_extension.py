#!/usr/bin/env python3
"""Extend the accepted 0–90 Phase 9 baseline to 120 s with topology vocabulary v1."""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

from build_climax_fork import (
    CLIMAX_LEAD_SECONDS,
    MAX_APPROACH_SLOPE_DEGREES,
    _clip_runways_around_overlay,
    _latest_traversable_approach,
    _ramp_surface_y,
    render_climax_fork_scene,
)
from build_spatial_score import build_spatial_score
from compile_geometry import (
    DANCER_CAPSULE_HEIGHT,
    FALL_LIMIT_Y,
    GRAVITY,
    GROUND_HEIGHT,
    GROUND_WIDTH,
    MERGE_LANDING_MARGIN,
    RUN_SPEED,
    compile_plan,
)
from fork_topology_vocabulary import (
    CRESCENDO_STAIRCASE,
    TIER_CONTRACT,
    classify_topology,
    previous_contiguous_window,
)
from render_spatial_geometry import apply_spatial_score


BASELINE_END_SECONDS = 90.0
EXTENSION_END_SECONDS = 120.0
BASELINE_END_X = BASELINE_END_SECONDS * RUN_SPEED
MIN_INTERVAL_LENGTH = 0.0001

STAIR_STEP_RISE = 0.28
STAIR_PLATFORM_LENGTH = 1.35
STAIR_GAP_LENGTH = 0.55
STAIR_MIN_STEPS = 3
STAIR_MAX_STEPS = 6
MERGE_CLEARANCE_FROM_NEXT_EVENT = 2.0


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


def _next_required_jump(
    output: dict[str, Any],
    target_time: float,
) -> dict[str, Any] | None:
    for event in output["events"]:
        if float(event["source_time"]) <= target_time:
            continue
        source_class = str(event["source_class"])
        if source_class.endswith("_JUMP") or source_class == "LARGE_TRAVELLING_LEAP":
            return event
    return None


def _apply_crescendo_staircase(
    output: dict[str, Any],
    visual_score: dict[str, Any],
    anchor: dict[str, Any],
    minimum_approach_x: float,
) -> dict[str, Any]:
    target_time = float(anchor["time"])
    target_event = next(
        event
        for event in output["events"]
        if abs(float(event["source_time"]) - target_time) <= 1e-6
    )
    if target_event["source_class"] != "LARGE_TRAVELLING_LEAP":
        raise ValueError("CRESCENDO_STAIRCASE requires LARGE_TRAVELLING_LEAP")

    climax_window = visual_score["windows"][int(anchor["window_index"])]
    build_window = previous_contiguous_window(
        visual_score,
        int(anchor["window_index"]),
    )
    if build_window is None or build_window["visual_intent"]["phrase_role"] != "BUILD":
        raise ValueError("CRESCENDO_STAIRCASE requires a contiguous BUILD")

    event_x = float(target_event["world"]["event_x"])
    safe_y = float(target_event["world"]["surface_y"])
    technical_base_y = _round(
        safe_y + GROUND_HEIGHT + 0.25 + DANCER_CAPSULE_HEIGHT + 0.05
    )
    split_x = _round(event_x - RUN_SPEED * CLIMAX_LEAD_SECONDS)
    entry_gap_length = float(target_event["geometry"]["gap_length"])
    entry_gap_end_x = _round(split_x + entry_gap_length)

    original_runways = output["surface_plan"]["runway_intervals"]
    approach_window, approach_start_y, approach_slope = _latest_traversable_approach(
        visual_score,
        original_runways,
        split_x,
        technical_base_y,
        safe_y,
        minimum_approach_x,
    )
    approach_start_x = _round(float(approach_window["start"]) * RUN_SPEED)
    approach_ramp = {
        "type": "APPROACH_RAMP",
        "start_x": approach_start_x,
        "end_x": split_x,
        "start_surface_y": approach_start_y,
        "end_surface_y": technical_base_y,
    }
    if approach_slope > MAX_APPROACH_SLOPE_DEGREES:
        raise ValueError("staircase approach exceeds traversable slope")

    beat_count = max(1, int(build_window["beat_span"]["count"]))
    step_count = max(STAIR_MIN_STEPS, min(STAIR_MAX_STEPS, beat_count))

    technical_segments: list[dict[str, Any]] = [{
        "type": "ENTRY_GAP",
        "start_x": split_x,
        "end_x": entry_gap_end_x,
        "surface_y": technical_base_y,
        "collision": False,
    }]

    cursor_x = entry_gap_end_x
    for index in range(step_count):
        surface_y = _round(technical_base_y + STAIR_STEP_RISE * index)
        platform_end = _round(cursor_x + STAIR_PLATFORM_LENGTH)
        technical_segments.append({
            "type": f"STAIR_STEP_{index + 1:02d}",
            "start_x": _round(cursor_x),
            "end_x": platform_end,
            "surface_y": surface_y,
            "collision": True,
        })
        cursor_x = platform_end
        if index < step_count - 1:
            gap_end = _round(cursor_x + STAIR_GAP_LENGTH)
            technical_segments.append({
                "type": f"STEP_GAP_{index + 1:02d}",
                "start_x": _round(cursor_x),
                "end_x": gap_end,
                "surface_y": surface_y,
                "collision": False,
                "optional_mastery_action": "JUMP",
                "failure_destination": "SAFE",
            })
            cursor_x = gap_end

    top_y = _round(technical_base_y + STAIR_STEP_RISE * (step_count - 1))
    next_jump = _next_required_jump(output, target_time)
    if next_jump is None:
        merge_x = _round(cursor_x + 8.0)
    else:
        merge_x = _round(
            float(next_jump["geometry"]["start_x"]) - MERGE_CLEARANCE_FROM_NEXT_EVENT
        )

    drop_height = top_y - safe_y
    drop_seconds = math.sqrt(2.0 * drop_height / GRAVITY)
    drop_distance = RUN_SPEED * drop_seconds
    technical_drop_x = _round(merge_x - drop_distance - MERGE_LANDING_MARGIN)
    if technical_drop_x <= cursor_x:
        raise ValueError("staircase has no room for top landing before merge")

    technical_segments.append({
        "type": "TOP_RUNWAY",
        "start_x": _round(cursor_x),
        "end_x": technical_drop_x,
        "surface_y": top_y,
        "collision": True,
    })
    technical_segments.append({
        "type": "DROP_MERGE",
        "start_x": technical_drop_x,
        "end_x": merge_x,
        "from_y": top_y,
        "to_y": _round(safe_y),
        "surface_y": top_y,
        "collision": False,
    })

    safe_standing_root_y = safe_y + DANCER_CAPSULE_HEIGHT / 2.0
    if safe_standing_root_y <= FALL_LIMIT_Y:
        raise ValueError("SAFE staircase route conflicts with fall limit")

    output["surface_plan"]["runway_intervals"] = _clip_runways_around_overlay(
        original_runways,
        approach_start_x,
        merge_x,
    )
    output["surface_plan"].setdefault("ramps", []).append(approach_ramp)

    for event in output["events"]:
        world_x = float(event["world"]["event_x"])
        if approach_start_x <= world_x < split_x and event is not target_event:
            event["world"]["surface_y"] = _round(
                _ramp_surface_y(approach_ramp, world_x)
            )

    target_event["world"]["surface_y"] = technical_base_y
    target_event["geometry"] = {
        "type": "ROUTE_FORK",
        "start_x": split_x,
        "end_x": merge_x,
    }
    target_event["preparation"]["runway_length"] = _round(
        split_x - approach_start_x
    )
    target_event["recovery"]["runway_length"] = _round(merge_x - event_x)
    target_event["branch"] = {
        "topology": CRESCENDO_STAIRCASE,
        "selection": (
            "climax jump enters TECHNICAL staircase; missed optional step jumps "
            "fail down to SAFE"
        ),
        "split": {
            "x": split_x,
            "shared_surface_y": technical_base_y,
            "no_jump_destination": "SAFE",
            "jump_destination": "TECHNICAL",
        },
        "routes": {
            "safe": {
                "elevation": _round(safe_y),
                "collision_geometry": {
                    "shape": "BOX",
                    "width": GROUND_WIDTH,
                    "thickness": GROUND_HEIGHT,
                },
                "segments": [{
                    "type": "LOWER_RUNWAY",
                    "start_x": split_x,
                    "end_x": merge_x,
                    "surface_y": _round(safe_y),
                    "collision": True,
                }],
                "descent": {
                    "type": "GRAVITY_DROP",
                    "start_x": split_x,
                    "landing_x": _round(
                        split_x
                        + RUN_SPEED
                        * math.sqrt(
                            2.0 * (technical_base_y - safe_y) / GRAVITY
                        )
                    ),
                    "drop_height": _round(technical_base_y - safe_y),
                    "standing_root_y": _round(safe_standing_root_y),
                    "fall_limit_y": FALL_LIMIT_Y,
                },
            },
            "technical": {
                "elevation": technical_base_y,
                "peak_elevation": top_y,
                "collision_geometry": {
                    "shape": "BOX",
                    "width": GROUND_WIDTH,
                    "thickness": GROUND_HEIGHT,
                },
                "segments": technical_segments,
                "optional_mastery_actions": step_count - 1,
                "failure_policy": "FAIL_DOWN_TO_SAFE",
            },
            "virtuoso": {
                "available": False,
                "future_contract": (
                    "compound aerial tier such as travelling leap plus turn; "
                    "failure falls to TECHNICAL or SAFE"
                ),
            },
        },
        "tiers": copy.deepcopy(TIER_CONTRACT),
        "merge": {
            "type": "TECHNICAL_DROP_TO_SAFE",
            "drop_start_x": technical_drop_x,
            "x": merge_x,
            "surface_y": _round(safe_y),
            "shared_runway_continues": True,
        },
    }
    target_event["explanation"].append(
        "contiguous BUILD plus major climax selected CRESCENDO_STAIRCASE"
    )
    target_event["explanation"].append(
        "narrow rising steps add optional mastery without adding required inputs"
    )

    return {
        "target_time": _round(target_time),
        "topology": CRESCENDO_STAIRCASE,
        "build_window": {
            "start": _round(build_window["start"]),
            "end": _round(build_window["end"]),
            "energy_delta": _round(build_window["metrics"]["energy_delta"]),
        },
        "climax_peak": _round(climax_window["metrics"]["climax_peak"]),
        "approach_ramp": approach_ramp,
        "approach_slope_degrees": _round(approach_slope),
        "step_count": step_count,
        "step_rise": STAIR_STEP_RISE,
        "platform_length": STAIR_PLATFORM_LENGTH,
        "gap_length": STAIR_GAP_LENGTH,
        "optional_mastery_actions": step_count - 1,
        "failure_policy": "FAIL_DOWN_TO_SAFE",
        "virtuoso_available": False,
        "new_required_actions": False,
    }


def build_120_second_extension(
    movement_demands: dict[str, Any],
    visual_score: dict[str, Any],
    accepted_90_plan: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if float(accepted_90_plan["compiled_time_range"]["end"]) != BASELINE_END_SECONDS:
        raise ValueError("accepted baseline must end at exactly 90 seconds")

    base_120 = compile_plan(movement_demands, EXTENSION_END_SECONDS)
    spatial_90_120 = build_spatial_score(
        visual_score,
        base_120,
        start_seconds=BASELINE_END_SECONDS,
        end_seconds=EXTENSION_END_SECONDS,
    )
    spatialized_120 = apply_spatial_score(base_120, spatial_90_120)

    output = copy.deepcopy(spatialized_120)
    output["events"] = [
        copy.deepcopy(event)
        for event in accepted_90_plan["events"]
        if float(event["source_time"]) <= BASELINE_END_SECONDS
    ] + [
        copy.deepcopy(event)
        for event in spatialized_120["events"]
        if float(event["source_time"]) > BASELINE_END_SECONDS
    ]
    output["surface_plan"]["runway_intervals"] = sorted(
        _clip_prefix_runways(
            accepted_90_plan["surface_plan"]["runway_intervals"],
            BASELINE_END_X,
        )
        + _clip_extension_runways(
            spatialized_120["surface_plan"]["runway_intervals"],
            BASELINE_END_X,
        ),
        key=lambda item: (item["start_x"], item["end_x"]),
    )
    output["surface_plan"]["ramps"] = copy.deepcopy(
        accepted_90_plan["surface_plan"].get("ramps", [])
    )

    selected: list[dict[str, Any]] = []
    minimum_approach_x = BASELINE_END_X
    for anchor in visual_score["event_anchors"]:
        time = float(anchor["time"])
        if not (BASELINE_END_SECONDS <= time < EXTENSION_END_SECONDS):
            continue
        topology = classify_topology(visual_score, anchor)
        if topology != CRESCENDO_STAIRCASE:
            continue
        overlay = _apply_crescendo_staircase(
            output,
            visual_score,
            anchor,
            minimum_approach_x,
        )
        selected.append(overlay)
        minimum_approach_x = float(
            next(
                event["branch"]["merge"]["x"]
                for event in output["events"]
                if abs(float(event["source_time"]) - time) <= 1e-6
            )
        )

    output["source_spatial_scores"] = list(
        accepted_90_plan.get("source_spatial_scores", [])
    ) + ["data/geometry/graceful_opening_90_120.spatial_score_v0_1.json"]
    output["source_visual_score"] = "data/music/graceful_opening.visual_score_v0_1.json"
    output["prototype_overlays"] = copy.deepcopy(
        accepted_90_plan.get("prototype_overlays", {})
    )
    output["prototype_overlays"]["fork_topology_vocabulary_v1"] = {
        "tiers": copy.deepcopy(TIER_CONTRACT),
        "extension_start": BASELINE_END_SECONDS,
        "extension_end": EXTENSION_END_SECONDS,
        "selected": selected,
        "new_required_actions": False,
    }

    return base_120, spatial_90_120, output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("movement_demands", type=Path)
    parser.add_argument("visual_score", type=Path)
    parser.add_argument("accepted_90_plan", type=Path)
    parser.add_argument("--base-plan-output", required=True, type=Path)
    parser.add_argument("--spatial-output", required=True, type=Path)
    parser.add_argument("--plan-output", required=True, type=Path)
    parser.add_argument("--scene-output", required=True, type=Path)
    args = parser.parse_args()

    movement_demands = json.loads(args.movement_demands.read_text(encoding="utf-8"))
    visual_score = json.loads(args.visual_score.read_text(encoding="utf-8"))
    accepted_90_plan = json.loads(args.accepted_90_plan.read_text(encoding="utf-8"))

    base_120, spatial_90_120, plan_120 = build_120_second_extension(
        movement_demands,
        visual_score,
        accepted_90_plan,
    )
    scene_120 = render_climax_fork_scene(plan_120)

    for path, payload in (
        (args.base_plan_output, base_120),
        (args.spatial_output, spatial_90_120),
        (args.plan_output, plan_120),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False)
            + "\n",
            encoding="utf-8",
        )

    args.scene_output.parent.mkdir(parents=True, exist_ok=True)
    args.scene_output.write_text(scene_120, encoding="utf-8")


if __name__ == "__main__":
    main()
