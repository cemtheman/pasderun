#!/usr/bin/env python3
"""Compile movement-demand candidates into deterministic Godot prototype geometry."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
RUN_SPEED = 4.0
COMPILE_END_SECONDS = 30.0
LEVEL_START_X = -4.0
LEVEL_END_X = COMPILE_END_SECONDS * RUN_SPEED + 8.0
GROUND_Y = -0.25
GROUND_HEIGHT = 0.5
GROUND_WIDTH = 4.0
BEAM_WIDTH = 0.8
BALANCE_AREA_WIDTH = 1.2
CONTEXT_SECONDS = 2.5
FORK_THRESHOLD = 0.90
FORK_CLASS_MARGIN = 0.12
MIN_FORK_DURATION_SECONDS = 2.5
DANCER_CAPSULE_HEIGHT = 2.0
DANCER_CAPSULE_RADIUS = 0.5
SAFE_HEAD_CLEARANCE = 0.25
CLEARANCE_EPSILON = 0.05
FALL_LIMIT_Y = -3.0
GRAVITY = 18.0
JUMP_VELOCITY = 6.0
TECHNICAL_ENTRY_CLEARANCE_MARGIN = 0.1
MERGE_LANDING_MARGIN = 0.5

GAP_CALIBRATION = {
    "SMALL_GAP": {"length": 1.2, "preparation": 6.0, "landing": 4.0},
    "MEDIUM_GAP": {"length": 1.7, "preparation": 8.0, "landing": 6.0},
    "LARGE_GAP": {"length": 2.2, "preparation": 10.0, "landing": 8.0},
}

CLASS_TO_GEOMETRY = {
    "TRAVEL": "RUNWAY",
    "ACCENT_ACTION": "ACCENT_ZONE",
    "SMALL_JUMP": "SMALL_GAP",
    "MEDIUM_JUMP": "MEDIUM_GAP",
    "LARGE_TRAVELLING_LEAP": "LARGE_GAP",
    "SUSTAINED_BALANCE": "BALANCE_PASSAGE",
    "TURN": "RUNWAY",
    "CONTROLLED_TRANSITION": "RUNWAY",
    "RECOVERY": "RECOVERY_RUNWAY",
}


def time_to_x(time_seconds: float) -> float:
    return round(time_seconds * RUN_SPEED, 4)


def _round(value: float) -> float:
    return round(float(value), 4)


def _has_viable_fork(
    event: dict[str, Any],
    next_time: float | None,
    current_surface_y: float,
) -> bool:
    if float(event["branchability"]) < FORK_THRESHOLD:
        return False
    candidates = event["candidate_classes"]
    if len(candidates) < 2:
        return False
    best = float(candidates[0]["confidence"])
    viable = [item for item in candidates if float(item["confidence"]) >= best - FORK_CLASS_MARGIN]
    if len(viable) < 2:
        return False
    if next_time is not None and next_time - float(event["time"]) < MIN_FORK_DURATION_SECONDS:
        return False
    if candidates[0]["class"] not in {"SMALL_JUMP", "MEDIUM_JUMP", "LARGE_TRAVELLING_LEAP"}:
        return False
    safe_surface_y = _safe_surface_y(current_surface_y)
    safe_standing_root_y = safe_surface_y + DANCER_CAPSULE_HEIGHT / 2.0
    return safe_standing_root_y > FALL_LIMIT_Y


def _safe_surface_y(technical_surface_y: float) -> float:
    technical_underside = technical_surface_y - GROUND_HEIGHT
    return _round(
        technical_underside
        - SAFE_HEAD_CLEARANCE
        - DANCER_CAPSULE_HEIGHT
        - CLEARANCE_EPSILON
    )


def _compile_event(
    event: dict[str, Any],
    next_time: float | None,
    current_surface_y: float,
    level_end_x: float = LEVEL_END_X,
) -> dict[str, Any]:
    source_time = float(event["time"])
    event_x = time_to_x(source_time)
    source_class = event["candidate_classes"][0]["class"]
    confidence = float(event["candidate_classes"][0]["confidence"])
    geometry_type = CLASS_TO_GEOMETRY[source_class]
    suppressed = [
        {"class": item["class"], "confidence": item["confidence"], "reason": "lower-ranked compatible inference retained as metadata"}
        for item in event["candidate_classes"][1:]
    ]
    output: dict[str, Any] = {
        "source_time": source_time,
        "source_class": source_class,
        "source_confidence": confidence,
        "world": {"event_x": event_x, "surface_y": _round(current_surface_y)},
        "geometry": {"type": geometry_type},
        "preparation": {"runway_length": _round(CONTEXT_SECONDS * RUN_SPEED)},
        "recovery": {"runway_length": _round(CONTEXT_SECONDS * RUN_SPEED)},
        "branch": None,
        "suppressed_inferences": suppressed,
        "explanation": [
            f"derived from {source_class} demand",
            f"event centered on music time {source_time:.3f}",
            f"world X derived by source_time × {RUN_SPEED:.1f}",
        ],
    }

    if geometry_type in GAP_CALIBRATION:
        calibration = GAP_CALIBRATION[geometry_type]
        half_gap = calibration["length"] / 2.0
        output["geometry"].update({
            "scale": geometry_type.removesuffix("_GAP"),
            "start_x": _round(event_x - half_gap),
            "end_x": _round(event_x + half_gap),
            "gap_length": calibration["length"],
            "landing_length": calibration["landing"],
        })
        output["preparation"]["runway_length"] = calibration["preparation"]
        output["recovery"]["runway_length"] = calibration["landing"]
    elif geometry_type == "BALANCE_PASSAGE":
        length = 6.0
        output["geometry"].update({
            "start_x": _round(event_x - length / 2.0),
            "end_x": _round(event_x + length / 2.0),
            "length": length,
            "width": BEAM_WIDTH,
            "area_width": BALANCE_AREA_WIDTH,
        })
    elif geometry_type == "ACCENT_ZONE":
        length = 1.2
        output["geometry"].update({
            "start_x": _round(event_x - length / 2.0),
            "end_x": _round(event_x + length / 2.0),
            "length": length,
        })
    else:
        output["geometry"].update({
            "start_x": _round(max(LEVEL_START_X, event_x - 2.0)),
            "end_x": _round(min(level_end_x, event_x + 2.0)),
        })

    if _has_viable_fork(event, next_time, current_surface_y):
        technical_type = CLASS_TO_GEOMETRY[source_class]
        calibration = GAP_CALIBRATION[technical_type]
        gap_start = event_x - calibration["length"] / 2.0
        gap_end = event_x + calibration["length"] / 2.0
        fork_start = max(LEVEL_START_X, event_x - calibration["preparation"])
        fork_end = min(
            level_end_x,
            event_x + calibration["landing"],
            time_to_x(next_time) - 2.0 if next_time is not None else level_end_x,
        )
        safe_surface_y = _safe_surface_y(current_surface_y)
        technical_underside_y = _round(current_surface_y - GROUND_HEIGHT)
        safe_dancer_top_y = _round(safe_surface_y + DANCER_CAPSULE_HEIGHT)
        safe_standing_root_y = _round(safe_surface_y + DANCER_CAPSULE_HEIGHT / 2.0)
        drop_height = current_surface_y - safe_surface_y
        drop_seconds = math.sqrt(2.0 * drop_height / GRAVITY)
        drop_distance = RUN_SPEED * drop_seconds
        technical_drop_x = fork_end - drop_distance - MERGE_LANDING_MARGIN
        entry_landing_x = fork_start + drop_distance + TECHNICAL_ENTRY_CLEARANCE_MARGIN
        if technical_drop_x <= gap_end:
            raise ValueError("fork duration cannot contain technical landing and physical merge")
        if safe_standing_root_y <= FALL_LIMIT_Y:
            raise ValueError("derived SAFE elevation conflicts with dancer fall limit")

        output["geometry"] = {
            "type": "ROUTE_FORK",
            "start_x": _round(fork_start),
            "end_x": _round(fork_end),
        }
        output["branch"] = {
            "selection": "no jump drops to LOWER SAFE; jump reaches UPPER TECHNICAL",
            "split": {
                "x": _round(fork_start),
                "shared_surface_y": _round(current_surface_y),
                "no_jump_destination": "SAFE",
                "jump_destination": "TECHNICAL",
            },
            "routes": {
                "safe": {
                    "elevation": safe_surface_y,
                    "collision_geometry": {
                        "shape": "BOX",
                        "width": GROUND_WIDTH,
                        "thickness": GROUND_HEIGHT,
                    },
                    "segments": [{
                        "type": "LOWER_RUNWAY",
                        "start_x": _round(fork_start),
                        "end_x": _round(fork_end),
                        "surface_y": safe_surface_y,
                        "collision": True,
                    }],
                    "descent": {
                        "type": "GRAVITY_DROP",
                        "start_x": _round(fork_start),
                        "landing_x": _round(fork_start + drop_distance),
                        "drop_height": _round(drop_height),
                        "drop_seconds": _round(drop_seconds),
                        "standing_root_y": safe_standing_root_y,
                        "fall_limit_y": FALL_LIMIT_Y,
                    },
                },
                "technical": {
                    "elevation": _round(current_surface_y),
                    "collision_geometry": {
                        "shape": "BOX",
                        "width": GROUND_WIDTH,
                        "thickness": GROUND_HEIGHT,
                    },
                    "segments": [
                        {
                            "type": "ENTRY_GAP",
                            "start_x": _round(fork_start),
                            "end_x": _round(entry_landing_x),
                            "surface_y": _round(current_surface_y),
                            "collision": False,
                        },
                        {
                            "type": "RUNWAY",
                            "start_x": _round(entry_landing_x),
                            "end_x": _round(gap_start),
                            "surface_y": _round(current_surface_y),
                            "collision": True,
                        },
                        {
                            "type": technical_type,
                            "start_x": _round(gap_start),
                            "end_x": _round(gap_end),
                            "surface_y": _round(current_surface_y),
                            "collision": False,
                        },
                        {
                            "type": "RUNWAY",
                            "start_x": _round(gap_end),
                            "end_x": _round(technical_drop_x),
                            "surface_y": _round(current_surface_y),
                            "collision": True,
                        },
                        {
                            "type": "DROP_MERGE",
                            "start_x": _round(technical_drop_x),
                            "end_x": _round(fork_end),
                            "from_y": _round(current_surface_y),
                            "to_y": safe_surface_y,
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
                "technical_underside_y": technical_underside_y,
                "safe_dancer_top_y": safe_dancer_top_y,
                "valid": safe_dancer_top_y < technical_underside_y - SAFE_HEAD_CLEARANCE,
            },
            "merge": {
                "type": "TECHNICAL_DROP_TO_SAFE",
                "drop_start_x": _round(technical_drop_x),
                "x": _round(fork_end),
                "surface_y": safe_surface_y,
                "shared_runway_continues": True,
            },
        }
        output["explanation"].append("high branchability and multiple viable classes generated optional SAFE/TECHNICAL routes")

    return output


def _subtract_intervals(base: list[tuple[float, float]], cuts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    result = base
    for cut_start, cut_end in sorted(cuts):
        next_result: list[tuple[float, float]] = []
        for start, end in result:
            if cut_end <= start or cut_start >= end:
                next_result.append((start, end))
                continue
            if cut_start > start:
                next_result.append((start, cut_start))
            if cut_end < end:
                next_result.append((cut_end, end))
        result = next_result
    return [(start, end) for start, end in result if end - start >= 0.1]


def compile_plan(
    movement_demands: dict[str, Any],
    compile_end_seconds: float = COMPILE_END_SECONDS,
) -> dict[str, Any]:
    if compile_end_seconds <= 0.0:
        raise ValueError("compile_end_seconds must be positive")
    level_end_x = compile_end_seconds * RUN_SPEED + 8.0
    source_events = [event for event in movement_demands["events"] if float(event["time"]) <= compile_end_seconds]
    events: list[dict[str, Any]] = []
    current_surface_y = 0.0
    for index, source_event in enumerate(source_events):
        next_time = float(source_events[index + 1]["time"]) if index + 1 < len(source_events) else None
        event = _compile_event(source_event, next_time, current_surface_y, level_end_x)
        events.append(event)
        if event["branch"] is not None:
            current_surface_y = float(event["branch"]["merge"]["surface_y"])

    mandatory_cuts: list[tuple[float, float]] = []
    balance_intervals: list[tuple[float, float, float]] = []
    for event in events:
        geometry = event["geometry"]
        if geometry["type"] in {"SMALL_GAP", "MEDIUM_GAP", "LARGE_GAP"}:
            mandatory_cuts.append((geometry["start_x"], geometry["end_x"]))
        elif geometry["type"] == "BALANCE_PASSAGE":
            interval = (geometry["start_x"], geometry["end_x"])
            mandatory_cuts.append(interval)
            balance_intervals.append((*interval, event["world"]["surface_y"]))
        elif geometry["type"] == "ROUTE_FORK":
            mandatory_cuts.append((geometry["start_x"], geometry["end_x"]))

    runway_intervals = _subtract_intervals([(LEVEL_START_X, level_end_x)], mandatory_cuts)

    def surface_at(start_x: float) -> float:
        surface_y = 0.0
        for event in events:
            if event["branch"] is not None and start_x >= event["branch"]["merge"]["x"]:
                surface_y = event["branch"]["merge"]["surface_y"]
        return surface_y

    return {
        "schema_version": SCHEMA_VERSION,
        "source_movement_demands": "data/choreography/graceful_opening.movement_demands_v0_1.json",
        "compiled_time_range": {"start": 0.0, "end": compile_end_seconds},
        "playable_world_extent": {"start_x": LEVEL_START_X, "end_x": _round(level_end_x)},
        "timebase": {
            "canonical_unit": "seconds",
            "run_speed_world_units_per_second": RUN_SPEED,
            "conversion": "event_x = source_time * run_speed_world_units_per_second",
        },
        "geometry_calibration_status": "prototype_controller_based",
        "controller_calibration": {
            "jump_velocity": JUMP_VELOCITY,
            "gravity": GRAVITY,
            "same_height_airtime_seconds": 0.6667,
            "same_height_horizontal_range": 2.6667,
            "capsule_height": DANCER_CAPSULE_HEIGHT,
            "capsule_radius": DANCER_CAPSULE_RADIUS,
            "fall_limit_y": FALL_LIMIT_Y,
            "note": "Gap lengths retain margin below the controller's ideal same-height ballistic range; humanoid/root-motion calibration is deferred.",
        },
        "gap_calibration": GAP_CALIBRATION,
        "geometry_vocabulary": [
            "RUNWAY", "LOW_PASSAGE", "SMALL_GAP", "MEDIUM_GAP", "LARGE_GAP",
            "BALANCE_PASSAGE", "ACCENT_ZONE", "RECOVERY_RUNWAY", "ROUTE_FORK", "MERGE",
        ],
        "events": events,
        "surface_plan": {
            "runway_intervals": [
                {"start_x": _round(start), "end_x": _round(end), "surface_y": _round(surface_at(start))}
                for start, end in runway_intervals
            ],
            "balance_intervals": [
                {"start_x": _round(start), "end_x": _round(end), "surface_y": _round(surface_y)}
                for start, end, surface_y in balance_intervals
            ],
        },
    }


def _box_resources(resources: list[str], size: tuple[float, float, float]) -> tuple[str, str]:
    index = len(resources) // 2 + 1
    mesh_id = f"BoxMesh_{index}"
    shape_id = f"BoxShape_{index}"
    size_text = f"Vector3({size[0]:.4f}, {size[1]:.4f}, {size[2]:.4f})"
    resources.extend([
        f'[sub_resource type="BoxMesh" id="{mesh_id}"]\nsize = {size_text}\n',
        f'[sub_resource type="BoxShape3D" id="{shape_id}"]\nsize = {size_text}\n',
    ])
    return mesh_id, shape_id


def _static_box(nodes: list[str], resources: list[str], name: str, start: float, end: float,
                width: float = GROUND_WIDTH, center_y: float = GROUND_Y) -> None:
    length = end - start
    center_x = (start + end) / 2.0
    mesh_id, shape_id = _box_resources(resources, (length, GROUND_HEIGHT, width))
    nodes.append(
        f'[node name="{name}" type="StaticBody3D" parent="Level"]\n'
        f'position = Vector3({center_x:.4f}, {center_y:.4f}, 0)\n'
        f'[node name="MeshInstance3D" type="MeshInstance3D" parent="Level/{name}"]\n'
        f'mesh = SubResource("{mesh_id}")\n'
        f'[node name="CollisionShape3D" type="CollisionShape3D" parent="Level/{name}"]\n'
        f'shape = SubResource("{shape_id}")\n'
    )


def render_scene(plan: dict[str, Any]) -> str:
    resources: list[str] = []
    nodes: list[str] = []
    for index, interval in enumerate(plan["surface_plan"]["runway_intervals"], start=1):
        _static_box(
            nodes,
            resources,
            f"Runway{index:02d}",
            interval["start_x"],
            interval["end_x"],
            center_y=interval["surface_y"] - GROUND_HEIGHT / 2.0,
        )

    for index, event in enumerate(plan["events"], start=1):
        geometry = event["geometry"]
        if geometry["type"] == "BALANCE_PASSAGE":
            name = f"BalancePassage{index:02d}"
            surface_y = event["world"]["surface_y"]
            _static_box(
                nodes,
                resources,
                name,
                geometry["start_x"],
                geometry["end_x"],
                BEAM_WIDTH,
                surface_y - GROUND_HEIGHT / 2.0,
            )
            _, area_shape = _box_resources(resources, (geometry["length"], 2.0, BALANCE_AREA_WIDTH))
            nodes.append(
                f'[node name="BalanceArea" type="Area3D" parent="Level/{name}"]\n'
                f'position = Vector3(0, 1, 0)\nscript = ExtResource("1_balance")\n'
                f'[node name="CollisionShape3D" type="CollisionShape3D" parent="Level/{name}/BalanceArea"]\n'
                f'shape = SubResource("{area_shape}")\n'
            )
        elif geometry["type"] == "ACCENT_ZONE":
            _, shape_id = _box_resources(resources, (geometry["length"], 2.0, GROUND_WIDTH))
            nodes.append(
                f'[node name="AccentZone{index:02d}" type="Area3D" parent="Level"]\n'
                f'position = Vector3({event["world"]["event_x"]:.4f}, {event["world"]["surface_y"] + 1.0:.4f}, 0)\n'
                f'[node name="CollisionShape3D" type="CollisionShape3D" parent="Level/AccentZone{index:02d}"]\n'
                f'shape = SubResource("{shape_id}")\n'
            )
        elif geometry["type"] == "ROUTE_FORK":
            branch = event["branch"]
            safe = branch["routes"]["safe"]
            technical = branch["routes"]["technical"]
            safe_segment = safe["segments"][0]
            _static_box(
                nodes,
                resources,
                f"SafeLowerRoute{index:02d}",
                safe_segment["start_x"],
                safe_segment["end_x"],
                GROUND_WIDTH,
                safe["elevation"] - GROUND_HEIGHT / 2.0,
            )
            technical_runways = [segment for segment in technical["segments"] if segment["collision"]]
            for segment_index, segment in enumerate(technical_runways, start=1):
                _static_box(
                    nodes,
                    resources,
                    f"TechnicalRoute{index:02d}_{segment_index:02d}",
                    segment["start_x"],
                    segment["end_x"],
                    GROUND_WIDTH,
                    technical["elevation"] - GROUND_HEIGHT / 2.0,
                )
            nodes.append(
                f'[node name="ForkStart{index:02d}" type="Marker3D" parent="Level"]\n'
                f'position = Vector3({geometry["start_x"]:.4f}, {branch["split"]["shared_surface_y"]:.4f}, 0)\n'
                f'[node name="ForkMerge{index:02d}" type="Marker3D" parent="Level"]\n'
                f'position = Vector3({branch["merge"]["x"]:.4f}, {branch["merge"]["surface_y"]:.4f}, 0)\n'
            )

        nodes.append(
            f'[node name="Event{index:02d}_{event["source_class"]}" type="Marker3D" parent="Events"]\n'
            f'position = Vector3({event["world"]["event_x"]:.4f}, {event["world"]["surface_y"]:.4f}, 0)\n'
        )

    header = (
        f'[gd_scene load_steps={len(resources) + 2} format=3]\n\n'
        '[ext_resource type="Script" path="res://scenes/gameplay/balance_area.gd" id="1_balance"]\n\n'
    )
    end_seconds = float(plan["compiled_time_range"]["end"])
    root_name = f"GracefulOpening{int(round(end_seconds)):04d}"
    return header + "\n".join(resources) + f"\n[node name=\"{root_name}\" type=\"Node3D\"]\n\n[node name=\"Level\" type=\"Node3D\" parent=\".\"]\n\n[node name=\"Events\" type=\"Node3D\" parent=\".\"]\n\n" + "\n".join(nodes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("movement_demands", type=Path)
    parser.add_argument("--plan-output", required=True, type=Path)
    parser.add_argument("--scene-output", required=True, type=Path)
    parser.add_argument("--compile-end-seconds", type=float, default=COMPILE_END_SECONDS)
    args = parser.parse_args()
    movement_demands = json.loads(args.movement_demands.read_text(encoding="utf-8"))
    plan = compile_plan(movement_demands, args.compile_end_seconds)
    args.plan_output.parent.mkdir(parents=True, exist_ok=True)
    args.scene_output.parent.mkdir(parents=True, exist_ok=True)
    args.plan_output.write_text(json.dumps(plan, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    args.scene_output.write_text(render_scene(plan), encoding="utf-8")


if __name__ == "__main__":
    main()
