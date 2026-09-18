#!/usr/bin/env python3
"""Build the strongest 30–60 s climax as a single-input SAFE/TECHNICAL fork.

This is a Phase 9 prototype overlay. The accepted base geometry and Spatial
Score remain intact. The derived plan replaces only the BUILD approach and the
selected climax event, then renders a separate Godot scene.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
from pathlib import Path
from typing import Any

from compile_geometry import (
    CLEARANCE_EPSILON,
    DANCER_CAPSULE_HEIGHT,
    DANCER_CAPSULE_RADIUS,
    FALL_LIMIT_Y,
    GRAVITY,
    GROUND_HEIGHT,
    GROUND_WIDTH,
    MERGE_LANDING_MARGIN,
    RUN_SPEED,
    SAFE_HEAD_CLEARANCE,
    render_scene,
)
from render_spatial_geometry import apply_spatial_score


SLICE_START_SECONDS = 30.0
SLICE_END_SECONDS = 60.0
CLIMAX_LEAD_SECONDS = 0.40
MAX_APPROACH_SLOPE_DEGREES = 20.0
MIN_INTERVAL_LENGTH = 0.0001


def _round(value: float) -> float:
    return round(float(value), 4)


def _strongest_climax_jump(
    visual_score: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    windows = visual_score["windows"]
    candidates: list[tuple[float, float, dict[str, Any], dict[str, Any]]] = []

    for anchor in visual_score["event_anchors"]:
        time = float(anchor["time"])
        interaction = anchor["interaction"]
        if not (SLICE_START_SECONDS <= time < SLICE_END_SECONDS):
            continue
        if not bool(interaction["required"]):
            continue
        if interaction["candidate_action"] != "JUMP":
            continue

        window = windows[int(anchor["window_index"])]
        if window["visual_intent"]["phrase_role"] != "CLIMAX":
            continue
        candidates.append((
            float(window["metrics"]["climax_peak"]),
            float(window["visual_intent"]["intensity"]),
            anchor,
            window,
        ))

    if not candidates:
        raise ValueError("no required climax jump exists in the Phase 9 slice")

    _, _, anchor, window = max(candidates, key=lambda item: (item[0], item[1]))
    return anchor, window


def _previous_build_window(
    visual_score: dict[str, Any],
    target_window: dict[str, Any],
) -> dict[str, Any]:
    windows = visual_score["windows"]
    target_index = windows.index(target_window)
    for index in range(target_index - 1, -1, -1):
        window = windows[index]
        if window["visual_intent"]["phrase_role"] == "BUILD":
            return window
        if float(target_window["start"]) - float(window["end"]) > 0.05:
            break
    raise ValueError("selected climax has no contiguous BUILD approach window")


def _clip_runways_around_overlay(
    intervals: list[dict[str, Any]],
    start_x: float,
    end_x: float,
) -> list[dict[str, float]]:
    output: list[dict[str, float]] = []
    for interval in intervals:
        left = float(interval["start_x"])
        right = float(interval["end_x"])
        surface_y = float(interval["surface_y"])

        if right <= start_x or left >= end_x:
            output.append(copy.deepcopy(interval))
            continue
        if left < start_x and start_x - left >= MIN_INTERVAL_LENGTH:
            output.append({
                "start_x": _round(left),
                "end_x": _round(start_x),
                "surface_y": _round(surface_y),
            })
        if right > end_x and right - end_x >= MIN_INTERVAL_LENGTH:
            output.append({
                "start_x": _round(end_x),
                "end_x": _round(right),
                "surface_y": _round(surface_y),
            })
    return sorted(output, key=lambda item: (item["start_x"], item["end_x"]))


def _surface_before(
    intervals: list[dict[str, Any]],
    world_x: float,
    fallback: float,
) -> float:
    matches = [
        interval for interval in intervals
        if abs(float(interval["end_x"]) - world_x) <= 1e-4
    ]
    if matches:
        return float(matches[-1]["surface_y"])
    return fallback


def _ramp_surface_y(ramp: dict[str, float], world_x: float) -> float:
    progress = (
        (world_x - float(ramp["start_x"]))
        / (float(ramp["end_x"]) - float(ramp["start_x"]))
    )
    progress = max(0.0, min(1.0, progress))
    return (
        float(ramp["start_surface_y"])
        + (float(ramp["end_surface_y"]) - float(ramp["start_surface_y"])) * progress
    )


def build_climax_fork_plan(
    base_plan: dict[str, Any],
    spatial_score: dict[str, Any],
    visual_score: dict[str, Any],
) -> dict[str, Any]:
    output = apply_spatial_score(base_plan, spatial_score)
    anchor, climax_window = _strongest_climax_jump(visual_score)
    build_window = _previous_build_window(visual_score, climax_window)

    target_time = float(anchor["time"])
    target_event = next(
        (event for event in output["events"] if abs(float(event["source_time"]) - target_time) <= 1e-6),
        None,
    )
    if target_event is None:
        raise ValueError("selected climax event does not exist in geometry plan")
    if target_event["source_class"] != "LARGE_TRAVELLING_LEAP":
        raise ValueError("climax fork prototype requires a LARGE_TRAVELLING_LEAP")

    event_x = float(target_event["world"]["event_x"])
    safe_y = float(target_event["world"]["surface_y"])
    technical_y = _round(
        safe_y
        + GROUND_HEIGHT
        + SAFE_HEAD_CLEARANCE
        + DANCER_CAPSULE_HEIGHT
        + CLEARANCE_EPSILON
    )

    gap_length = float(target_event["geometry"]["gap_length"])
    split_x = _round(event_x - RUN_SPEED * CLIMAX_LEAD_SECONDS)
    gap_end_x = _round(split_x + gap_length)
    merge_x = _round(event_x + float(target_event["recovery"]["runway_length"]))
    approach_start_x = _round(float(build_window["start"]) * RUN_SPEED)

    original_spatial_runways = output["surface_plan"]["runway_intervals"]
    approach_start_y = _surface_before(original_spatial_runways, approach_start_x, safe_y)
    ramp = {
        "type": "APPROACH_RAMP",
        "start_x": approach_start_x,
        "end_x": split_x,
        "start_surface_y": _round(approach_start_y),
        "end_surface_y": technical_y,
    }

    run = split_x - approach_start_x
    rise = technical_y - approach_start_y
    slope_degrees = math.degrees(math.atan2(rise, run))
    if slope_degrees > MAX_APPROACH_SLOPE_DEGREES:
        raise ValueError("climax approach ramp exceeds prototype slope limit")

    drop_height = technical_y - safe_y
    drop_seconds = math.sqrt(2.0 * drop_height / GRAVITY)
    drop_distance = RUN_SPEED * drop_seconds
    safe_landing_x = split_x + drop_distance
    technical_drop_x = merge_x - drop_distance - MERGE_LANDING_MARGIN
    if technical_drop_x <= gap_end_x:
        raise ValueError("climax fork cannot contain upper landing and merge")

    safe_standing_root_y = safe_y + DANCER_CAPSULE_HEIGHT / 2.0
    technical_underside_y = technical_y - GROUND_HEIGHT
    safe_dancer_top_y = safe_y + DANCER_CAPSULE_HEIGHT
    clearance_valid = safe_dancer_top_y < technical_underside_y - SAFE_HEAD_CLEARANCE
    if safe_standing_root_y <= FALL_LIMIT_Y or not clearance_valid:
        raise ValueError("climax fork clearance conflicts with controller safety")

    output["surface_plan"]["runway_intervals"] = _clip_runways_around_overlay(
        original_spatial_runways,
        approach_start_x,
        merge_x,
    )
    output["surface_plan"]["ramps"] = [ramp]

    for event in output["events"]:
        world_x = float(event["world"]["event_x"])
        if approach_start_x <= world_x < split_x and event is not target_event:
            event["world"]["surface_y"] = _round(_ramp_surface_y(ramp, world_x))

    target_event["world"]["surface_y"] = technical_y
    target_event["geometry"] = {
        "type": "ROUTE_FORK",
        "start_x": split_x,
        "end_x": merge_x,
    }
    target_event["preparation"]["runway_length"] = _round(split_x - approach_start_x)
    target_event["recovery"]["runway_length"] = _round(merge_x - event_x)
    target_event["branch"] = {
        "selection": "no jump drops to LOWER SAFE; one climax jump reaches UPPER TECHNICAL",
        "split": {
            "x": split_x,
            "shared_surface_y": technical_y,
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
                    "landing_x": _round(safe_landing_x),
                    "drop_height": _round(drop_height),
                    "drop_seconds": _round(drop_seconds),
                    "standing_root_y": _round(safe_standing_root_y),
                    "fall_limit_y": FALL_LIMIT_Y,
                },
            },
            "technical": {
                "elevation": technical_y,
                "collision_geometry": {
                    "shape": "BOX",
                    "width": GROUND_WIDTH,
                    "thickness": GROUND_HEIGHT,
                },
                "segments": [
                    {
                        "type": "LARGE_GAP",
                        "start_x": split_x,
                        "end_x": gap_end_x,
                        "surface_y": technical_y,
                        "collision": False,
                    },
                    {
                        "type": "RUNWAY",
                        "start_x": gap_end_x,
                        "end_x": _round(technical_drop_x),
                        "surface_y": technical_y,
                        "collision": True,
                    },
                    {
                        "type": "DROP_MERGE",
                        "start_x": _round(technical_drop_x),
                        "end_x": merge_x,
                        "from_y": technical_y,
                        "to_y": _round(safe_y),
                        "collision": False,
                    },
                ],
            },
        },
        "clearance": {
            "capsule_height": DANCER_CAPSULE_HEIGHT,
            "capsule_radius": DANCER_CAPSULE_RADIUS,
            "platform_thickness": GROUND_HEIGHT,
            "safety_margin": SAFE_HEAD_CLEARANCE,
            "technical_underside_y": _round(technical_underside_y),
            "safe_dancer_top_y": _round(safe_dancer_top_y),
            "valid": clearance_valid,
        },
        "merge": {
            "type": "TECHNICAL_DROP_TO_SAFE",
            "drop_start_x": _round(technical_drop_x),
            "x": merge_x,
            "surface_y": _round(safe_y),
            "shared_runway_continues": True,
        },
    }
    target_event["explanation"].append(
        "strongest Phase 9 climax converted to a single-input SAFE/TECHNICAL fork"
    )
    target_event["explanation"].append(
        "BUILD approach rises on a traversable ramp; climax JUMP selects upper route"
    )

    output["source_spatial_score"] = "data/geometry/graceful_opening_30_60.spatial_score_v0_1.json"
    output["source_visual_score"] = "data/music/graceful_opening.visual_score_v0_1.json"
    output["prototype_overlays"] = {
        "climax_fork_v0_1": {
            "target_time": _round(target_time),
            "climax_peak": _round(climax_window["metrics"]["climax_peak"]),
            "intensity": _round(climax_window["visual_intent"]["intensity"]),
            "build_window_start": _round(build_window["start"]),
            "approach_ramp": ramp,
            "approach_slope_degrees": _round(slope_degrees),
            "split_x": split_x,
            "merge_x": merge_x,
            "required_action": "JUMP",
            "new_required_actions": False,
        }
    }
    return output


def _ramp_scene_fragments(
    ramps: list[dict[str, Any]],
) -> tuple[str, str]:
    resources: list[str] = []
    nodes: list[str] = []

    for index, ramp in enumerate(ramps, start=1):
        start_x = float(ramp["start_x"])
        end_x = float(ramp["end_x"])
        start_y = float(ramp["start_surface_y"])
        end_y = float(ramp["end_surface_y"])
        dx = end_x - start_x
        dy = end_y - start_y
        length = math.hypot(dx, dy)
        angle = math.atan2(dy, dx)
        normal_x = -math.sin(angle)
        normal_y = math.cos(angle)
        midpoint_x = (start_x + end_x) * 0.5
        midpoint_y = (start_y + end_y) * 0.5
        center_x = midpoint_x - normal_x * GROUND_HEIGHT * 0.5
        center_y = midpoint_y - normal_y * GROUND_HEIGHT * 0.5

        mesh_id = f"ClimaxRampMesh_{index}"
        shape_id = f"ClimaxRampShape_{index}"
        resources.extend([
            (
                f'[sub_resource type="BoxMesh" id="{mesh_id}"]\n'
                'material = ExtResource("2_palace")\n'
                f'size = Vector3({length:.4f}, {GROUND_HEIGHT:.4f}, {GROUND_WIDTH:.4f})\n'
            ),
            (
                f'[sub_resource type="BoxShape3D" id="{shape_id}"]\n'
                f'size = Vector3({length:.4f}, {GROUND_HEIGHT:.4f}, {GROUND_WIDTH:.4f})\n'
            ),
        ])
        nodes.append(
            f'[node name="ClimaxApproachRamp{index:02d}" type="StaticBody3D" parent="Level"]\n'
            f'position = Vector3({center_x:.4f}, {center_y:.4f}, 0)\n'
            f'rotation = Vector3(0, 0, {angle:.6f})\n'
            f'[node name="MeshInstance3D" type="MeshInstance3D" parent="Level/ClimaxApproachRamp{index:02d}"]\n'
            f'mesh = SubResource("{mesh_id}")\n'
            f'[node name="CollisionShape3D" type="CollisionShape3D" parent="Level/ClimaxApproachRamp{index:02d}"]\n'
            f'shape = SubResource("{shape_id}")\n'
        )

    return "\n".join(resources), "\n".join(nodes)


def render_climax_fork_scene(plan: dict[str, Any]) -> str:
    scene = render_scene(plan)
    ramps = plan["surface_plan"].get("ramps", [])
    resources, nodes = _ramp_scene_fragments(ramps)

    header = re.search(r"\[gd_scene load_steps=(\d+) format=3\]", scene)
    if header is None:
        raise ValueError("rendered scene load_steps header was not found")
    load_steps = int(header.group(1)) + len(ramps) * 2
    scene = scene[:header.start()] + f"[gd_scene load_steps={load_steps} format=3]" + scene[header.end():]

    root_marker = '[node name="GracefulOpening0060" type="Node3D"]'
    if root_marker not in scene:
        raise ValueError("expected 60 second root was not found")
    scene = scene.replace(
        root_marker,
        '[node name="GracefulOpening0060ClimaxFork" type="Node3D"]',
        1,
    )
    scene = scene.replace(
        '[node name="GracefulOpening0060ClimaxFork" type="Node3D"]',
        resources + '\n[node name="GracefulOpening0060ClimaxFork" type="Node3D"]',
        1,
    )
    return scene + "\n" + nodes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_geometry_plan", type=Path)
    parser.add_argument("spatial_score", type=Path)
    parser.add_argument("visual_score", type=Path)
    parser.add_argument("--plan-output", required=True, type=Path)
    parser.add_argument("--scene-output", required=True, type=Path)
    args = parser.parse_args()

    base_plan = json.loads(args.base_geometry_plan.read_text(encoding="utf-8"))
    spatial_score = json.loads(args.spatial_score.read_text(encoding="utf-8"))
    visual_score = json.loads(args.visual_score.read_text(encoding="utf-8"))
    plan = build_climax_fork_plan(base_plan, spatial_score, visual_score)
    scene = render_climax_fork_scene(plan)

    args.plan_output.parent.mkdir(parents=True, exist_ok=True)
    args.scene_output.parent.mkdir(parents=True, exist_ok=True)
    args.plan_output.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    args.scene_output.write_text(scene, encoding="utf-8")


if __name__ == "__main__":
    main()
