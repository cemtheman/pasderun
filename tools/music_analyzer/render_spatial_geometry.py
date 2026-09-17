#!/usr/bin/env python3
"""Render a Spatial Score as a distinct Godot level scene.

The accepted base geometry plan remains authoritative for event geometry.
Only runway intervals inside the Spatial Score world range are replaced.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from compile_geometry import render_scene


MIN_INTERVAL_LENGTH = 0.0001


def _round(value: float) -> float:
    return round(float(value), 4)


def apply_spatial_score(
    base_plan: dict[str, Any],
    spatial_score: dict[str, Any],
) -> dict[str, Any]:
    if not bool(spatial_score["policy"]["event_geometry_preserved"]):
        raise ValueError("spatial score must preserve accepted event geometry")
    if bool(spatial_score["policy"]["new_gaps"]):
        raise ValueError("spatial score renderer does not accept new gaps")
    if bool(spatial_score["policy"]["new_required_actions"]):
        raise ValueError("spatial score renderer does not accept new required actions")

    start_x = float(spatial_score["world_range"]["start_x"])
    end_x = float(spatial_score["world_range"]["end_x"])
    if end_x <= start_x:
        raise ValueError("spatial score world range must be positive")

    output = copy.deepcopy(base_plan)
    original_runways = base_plan["surface_plan"]["runway_intervals"]
    replacement_runways: list[dict[str, float]] = []

    for runway in original_runways:
        runway_start = float(runway["start_x"])
        runway_end = float(runway["end_x"])
        surface_y = float(runway["surface_y"])

        if runway_end <= start_x or runway_start >= end_x:
            replacement_runways.append(copy.deepcopy(runway))
            continue

        if runway_start < start_x and start_x - runway_start >= MIN_INTERVAL_LENGTH:
            replacement_runways.append({
                "start_x": _round(runway_start),
                "end_x": _round(start_x),
                "surface_y": _round(surface_y),
            })

        if runway_end > end_x and runway_end - end_x >= MIN_INTERVAL_LENGTH:
            replacement_runways.append({
                "start_x": _round(end_x),
                "end_x": _round(runway_end),
                "surface_y": _round(surface_y),
            })

    for segment in spatial_score["segments"]:
        segment_start = float(segment["start_x"])
        segment_end = float(segment["end_x"])
        if segment_end - segment_start < MIN_INTERVAL_LENGTH:
            continue
        if segment_start < start_x - 1e-6 or segment_end > end_x + 1e-6:
            raise ValueError("spatial segment escapes declared world range")
        replacement_runways.append({
            "start_x": _round(segment_start),
            "end_x": _round(segment_end),
            "surface_y": _round(segment["surface_y"]),
        })

    replacement_runways.sort(key=lambda interval: (interval["start_x"], interval["end_x"]))
    output["surface_plan"]["runway_intervals"] = replacement_runways
    return output


def render_spatial_scene(
    base_plan: dict[str, Any],
    spatial_score: dict[str, Any],
) -> str:
    transformed = apply_spatial_score(base_plan, spatial_score)
    scene = render_scene(transformed)

    end_seconds = float(base_plan["compiled_time_range"]["end"])
    base_root = f'[node name="GracefulOpening{int(round(end_seconds)):04d}" type="Node3D"]'
    spatial_root = f'[node name="GracefulOpening{int(round(end_seconds)):04d}Spatial" type="Node3D"]'
    if base_root not in scene:
        raise ValueError("rendered base root was not found")
    return scene.replace(base_root, spatial_root, 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_geometry_plan", type=Path)
    parser.add_argument("spatial_score", type=Path)
    parser.add_argument("--scene-output", required=True, type=Path)
    args = parser.parse_args()

    base_plan = json.loads(args.base_geometry_plan.read_text(encoding="utf-8"))
    spatial_score = json.loads(args.spatial_score.read_text(encoding="utf-8"))
    scene = render_spatial_scene(base_plan, spatial_score)

    args.scene_output.parent.mkdir(parents=True, exist_ok=True)
    args.scene_output.write_text(scene, encoding="utf-8")


if __name__ == "__main__":
    main()
