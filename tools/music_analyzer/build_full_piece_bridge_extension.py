#!/usr/bin/env python3
"""Extend the accepted 0–120 Phase 9 baseline through the full music duration.

The accepted 0–120 event/topology contract is frozen. The 120–end extension
keeps Visual Score actions authoritative and introduces one shared-route BRIDGE
span for the final consecutive SUSTAIN + LEGATO phrase.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from build_climax_fork import render_climax_fork_scene
from build_spatial_score import build_spatial_score
from compile_geometry import RUN_SPEED, compile_plan
from fork_topology_vocabulary import BRIDGE
from render_spatial_geometry import apply_spatial_score


BASELINE_END_SECONDS = 120.0
BASELINE_END_X = BASELINE_END_SECONDS * RUN_SPEED
MIN_INTERVAL_LENGTH = 0.0001
BRIDGE_MIN_CONTINUITY = 0.70
BRIDGE_MIN_SUSTAIN = 0.65
PHASE11_DENSITY_GAP_LENGTH = 1.3
PHASE11_DENSITY_GAP_TIMES = (43.862, 46.208, 56.889)


def _round(value: float) -> float:
    return round(float(value), 4)


def _full_end_seconds(visual_score: dict[str, Any]) -> float:
    windows = visual_score["windows"]
    if not windows:
        raise ValueError("visual score has no windows")
    return float(windows[-1]["end"])


def _clip_prefix_runways(
    intervals: list[dict[str, Any]],
    boundary_x: float,
) -> list[dict[str, float]]:
    output: list[dict[str, float]] = []
    for interval in intervals:
        left = float(interval["start_x"])
        right = min(float(interval["end_x"]), boundary_x)
        if left >= boundary_x or right - left < MIN_INTERVAL_LENGTH:
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
        if right <= boundary_x or right - left < MIN_INTERVAL_LENGTH:
            continue
        output.append({
            "start_x": _round(left),
            "end_x": _round(right),
            "surface_y": _round(interval["surface_y"]),
        })
    return output


def _apply_phase11_density_gaps(
    intervals: list[dict[str, Any]],
) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
    output = [copy.deepcopy(interval) for interval in intervals]
    gaps: list[dict[str, float]] = []

    for source_time in PHASE11_DENSITY_GAP_TIMES:
        center_x = source_time * RUN_SPEED
        half = PHASE11_DENSITY_GAP_LENGTH / 2.0
        gap_start = center_x - half
        gap_end = center_x + half

        coverage = 0.0
        next_output: list[dict[str, float]] = []
        for interval in output:
            left = float(interval["start_x"])
            right = float(interval["end_x"])
            surface_y = float(interval["surface_y"])
            overlap_start = max(left, gap_start)
            overlap_end = min(right, gap_end)

            if overlap_end <= overlap_start:
                next_output.append(copy.deepcopy(interval))
                continue

            coverage += overlap_end - overlap_start
            if left < gap_start and gap_start - left >= MIN_INTERVAL_LENGTH:
                next_output.append({
                    "start_x": _round(left),
                    "end_x": _round(gap_start),
                    "surface_y": _round(surface_y),
                })
            if right > gap_end and right - gap_end >= MIN_INTERVAL_LENGTH:
                next_output.append({
                    "start_x": _round(gap_end),
                    "end_x": _round(right),
                    "surface_y": _round(surface_y),
                })

        if coverage < PHASE11_DENSITY_GAP_LENGTH - 1e-3:
            raise ValueError(
                f"Phase 11 density gap at t={source_time:.3f} lacks runway coverage"
            )

        output = sorted(
            next_output,
            key=lambda item: (float(item["start_x"]), float(item["end_x"])),
        )
        gaps.append({
            "source_time": _round(source_time),
            "center_x": _round(center_x),
            "start_x": _round(gap_start),
            "end_x": _round(gap_end),
            "gap_length": PHASE11_DENSITY_GAP_LENGTH,
        })

    return output, gaps


def _select_final_bridge_windows(
    visual_score: dict[str, Any],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for window in reversed(visual_score["windows"]):
        role = str(window["visual_intent"]["phrase_role"])
        articulation = str(window["visual_intent"]["articulation"])
        continuity = float(window["visual_intent"]["continuity"])
        sustain = float(window["metrics"]["sustain"])
        if (
            role == "SUSTAIN"
            and articulation == "LEGATO"
            and continuity >= BRIDGE_MIN_CONTINUITY
            and sustain >= BRIDGE_MIN_SUSTAIN
        ):
            selected.append(window)
            continue
        if selected:
            break

    selected.reverse()
    if len(selected) < 2:
        raise ValueError("final BRIDGE requires at least two consecutive SUSTAIN/LEGATO windows")

    for left, right in zip(selected, selected[1:]):
        if abs(float(left["end"]) - float(right["start"])) > 0.01:
            raise ValueError("final BRIDGE windows are not contiguous")
    return selected


def _surface_y_at(
    intervals: list[dict[str, Any]],
    world_x: float,
) -> float:
    for interval in intervals:
        if float(interval["start_x"]) - 1e-6 <= world_x < float(interval["end_x"]) + 1e-6:
            return float(interval["surface_y"])
    raise ValueError(f"no runway covers bridge start x={world_x:.4f}")


def _flatten_bridge_span(
    intervals: list[dict[str, Any]],
    start_x: float,
    end_x: float,
) -> tuple[list[dict[str, float]], float]:
    if end_x <= start_x:
        raise ValueError("BRIDGE span must be positive")

    coverage = 0.0
    for interval in intervals:
        overlap_start = max(start_x, float(interval["start_x"]))
        overlap_end = min(end_x, float(interval["end_x"]))
        if overlap_end > overlap_start:
            coverage += overlap_end - overlap_start
    if coverage < (end_x - start_x) - 1e-3:
        raise ValueError("BRIDGE span crosses non-runway geometry")

    bridge_y = _surface_y_at(intervals, start_x)
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

    output.append({
        "start_x": _round(start_x),
        "end_x": _round(end_x),
        "surface_y": _round(bridge_y),
    })
    output.sort(key=lambda item: (float(item["start_x"]), float(item["end_x"])))
    return output, _round(bridge_y)


def build_full_piece_bridge_extension(
    movement_demands: dict[str, Any],
    visual_score: dict[str, Any],
    accepted_120_plan: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if float(accepted_120_plan["compiled_time_range"]["end"]) != BASELINE_END_SECONDS:
        raise ValueError("accepted baseline must end at exactly 120 seconds")

    full_end = _full_end_seconds(visual_score)
    if full_end <= BASELINE_END_SECONDS:
        raise ValueError("visual score does not extend beyond accepted baseline")

    base_full = compile_plan(movement_demands, full_end)
    spatial_120_end = build_spatial_score(
        visual_score,
        base_full,
        start_seconds=BASELINE_END_SECONDS,
        end_seconds=full_end,
    )
    spatialized_full = apply_spatial_score(base_full, spatial_120_end)

    output = copy.deepcopy(spatialized_full)
    output["events"] = [
        copy.deepcopy(event)
        for event in accepted_120_plan["events"]
        if float(event["source_time"]) <= BASELINE_END_SECONDS
    ] + [
        copy.deepcopy(event)
        for event in spatialized_full["events"]
        if float(event["source_time"]) > BASELINE_END_SECONDS
    ]

    stitched_runways = sorted(
        _clip_prefix_runways(
            accepted_120_plan["surface_plan"]["runway_intervals"],
            BASELINE_END_X,
        )
        + _clip_extension_runways(
            spatialized_full["surface_plan"]["runway_intervals"],
            BASELINE_END_X,
        ),
        key=lambda item: (float(item["start_x"]), float(item["end_x"])),
    )
    output["surface_plan"]["ramps"] = copy.deepcopy(
        accepted_120_plan["surface_plan"].get("ramps", [])
    )

    densified_runways, phase11_gaps = _apply_phase11_density_gaps(
        output["surface_plan"]["runway_intervals"]
    )
    output["surface_plan"]["runway_intervals"] = densified_runways
    output.setdefault("prototype_overlays", {})
    output["prototype_overlays"]["phase11_gameplay_density_v1"] = {
        "time_range": {"start": 30.0, "end": 60.0},
        "source": "MUSIC_ACCENT_SMALL_JUMP_UPLIFT",
        "new_required_actions": True,
        "gap_count": len(phase11_gaps),
        "gap_length": PHASE11_DENSITY_GAP_LENGTH,
        "gaps": phase11_gaps,
        "accepted_120_source_unchanged": True,
    }

    bridge_windows = _select_final_bridge_windows(visual_score)
    bridge_start = float(bridge_windows[0]["start"])
    bridge_end = float(bridge_windows[-1]["end"])
    bridge_start_x = bridge_start * RUN_SPEED
    bridge_end_x = bridge_end * RUN_SPEED

    flattened, bridge_y = _flatten_bridge_span(
        stitched_runways,
        bridge_start_x,
        bridge_end_x,
    )
    output["surface_plan"]["runway_intervals"] = flattened

    output["source_visual_score"] = "data/music/graceful_opening.visual_score_v0_1.json"
    output["source_spatial_scores"] = list(
        accepted_120_plan.get("source_spatial_scores", [])
    ) + ["data/geometry/graceful_opening_120_140.spatial_score_v0_1.json"]

    output["prototype_overlays"] = copy.deepcopy(
        accepted_120_plan.get("prototype_overlays", {})
    )
    output["prototype_overlays"]["architectural_spans_v1"] = [{
        "topology": BRIDGE,
        "shared_route": True,
        "start_time": _round(bridge_start),
        "end_time": _round(bridge_end),
        "start_x": _round(bridge_start_x),
        "end_x": _round(bridge_end_x),
        "surface_y": bridge_y,
        "source_roles": [
            str(window["visual_intent"]["phrase_role"])
            for window in bridge_windows
        ],
        "source_articulation": "LEGATO",
        "collision_profile": "FLAT_LEGATO_SPAN",
        "new_required_actions": False,
    }]

    return base_full, spatial_120_end, output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("movement_demands", type=Path)
    parser.add_argument("visual_score", type=Path)
    parser.add_argument("accepted_120_plan", type=Path)
    parser.add_argument("--base-plan-output", required=True, type=Path)
    parser.add_argument("--spatial-output", required=True, type=Path)
    parser.add_argument("--plan-output", required=True, type=Path)
    parser.add_argument("--scene-output", required=True, type=Path)
    args = parser.parse_args()

    movement_demands = json.loads(args.movement_demands.read_text(encoding="utf-8"))
    visual_score = json.loads(args.visual_score.read_text(encoding="utf-8"))
    accepted_120_plan = json.loads(args.accepted_120_plan.read_text(encoding="utf-8"))

    base_full, spatial_120_end, output = build_full_piece_bridge_extension(
        movement_demands,
        visual_score,
        accepted_120_plan,
    )
    scene = render_climax_fork_scene(output)

    for path, payload in (
        (args.base_plan_output, base_full),
        (args.spatial_output, spatial_120_end),
        (args.plan_output, output),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )

    args.scene_output.parent.mkdir(parents=True, exist_ok=True)
    args.scene_output.write_text(scene, encoding="utf-8")


if __name__ == "__main__":
    main()
