#!/usr/bin/env python3
"""Compile Visual Score windows into a playable passive spatial score.

This stage does not render a Godot scene. It preserves authored/accepted event
geometry and reshapes only existing runway coverage between required actions.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
DEFAULT_START_SECONDS = 30.0
DEFAULT_END_SECONDS = 60.0
MAX_PASSIVE_DELTA_Y = 0.15
MIN_SEGMENT_LENGTH = 0.0001
GEOMETRY_LOCK_ACTIONS = {"JUMP", "HOLD", "SWIPE_DOWN"}

ROLE_TO_PATTERN = {
    "CLIMAX": "LIFTED_TERRACE",
    "TURNING_POINT": "TURNING_TERRACE",
    "SUSTAIN": "LEGATO_SPAN",
    "BUILD": "RISING_TERRACE",
    "RELEASE": "FALLING_TERRACE",
    "PULSE": "PULSE_STEPS",
    "FLOW": "FLOWING_SPAN",
}


def _round(value: float) -> float:
    return round(float(value), 4)


def _clip(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _window_for_time(windows: list[dict[str, Any]], time: float) -> tuple[int, dict[str, Any]]:
    for index, window in enumerate(windows):
        start = float(window["start"])
        end = float(window["end"])
        if start <= time < end:
            return index, window
    if windows and abs(time - float(windows[-1]["end"])) <= 1e-6:
        return len(windows) - 1, windows[-1]
    raise ValueError(f"no visual-score window contains time {time:.4f}")


def _phase_index(window: dict[str, Any], time: float) -> tuple[int, int]:
    count = max(1, int(window["beat_span"]["count"]))
    start = float(window["start"])
    end = float(window["end"])
    progress = _clip((time - start) / max(end - start, 1e-9), 0.0, 0.999999)
    return min(count - 1, int(progress * count)), count


def _passive_delta(
    window: dict[str, Any],
    phase_index: int,
    phase_count: int,
) -> float:
    intent = window["visual_intent"]
    intensity = float(intent["intensity"])
    amplitude = min(MAX_PASSIVE_DELTA_Y, 0.05 + 0.10 * intensity)
    role = str(intent["phrase_role"])

    if role == "CLIMAX":
        center = (phase_count - 1) * 0.60
        distance = abs(phase_index - center) / max(1.0, phase_count * 0.60)
        factor = max(0.25, 1.0 - distance)
    elif role == "BUILD":
        factor = (phase_index + 1) / phase_count
    elif role == "RELEASE":
        factor = -(phase_index + 1) / phase_count
    elif role == "PULSE":
        factor = 0.70 if phase_index % 2 == 0 else -0.35
    elif role == "TURNING_POINT":
        factor = -0.45 if phase_index < phase_count / 2.0 else 0.45
    elif role == "SUSTAIN":
        factor = 0.20
    else:
        phase = (phase_index + 0.5) / phase_count
        factor = 0.30 * math.sin(phase * math.tau)

    return _round(_clip(amplitude * factor, -MAX_PASSIVE_DELTA_Y, MAX_PASSIVE_DELTA_Y))


def _action_locks(
    visual_score: dict[str, Any],
    start_seconds: float,
    end_seconds: float,
) -> list[dict[str, Any]]:
    gate = visual_score["playability_gate"]
    run_speed = float(gate["controller"]["run_speed"])
    reaction_lead = float(gate["design_limits"]["reaction_lead_seconds"])
    locks: list[dict[str, Any]] = []

    for anchor in visual_score["event_anchors"]:
        interaction = anchor["interaction"]
        if not bool(interaction["required"]):
            continue
        action = interaction["candidate_action"]
        if action not in GEOMETRY_LOCK_ACTIONS:
            continue
        time = float(anchor["time"])
        if time >= end_seconds:
            continue
        occupancy = float(interaction["occupancy_seconds"])
        lock_start_time = max(start_seconds, time - reaction_lead)
        lock_end_time = min(end_seconds, time + occupancy)
        if lock_end_time <= start_seconds or lock_start_time >= end_seconds:
            continue
        if lock_end_time <= lock_start_time:
            continue
        locks.append({
            "time": _round(time),
            "action": action,
            "start_time": _round(lock_start_time),
            "end_time": _round(lock_end_time),
            "start_x": _round(lock_start_time * run_speed),
            "end_x": _round(lock_end_time * run_speed),
        })

    return locks


def _lock_at_x(locks: list[dict[str, Any]], world_x: float) -> dict[str, Any] | None:
    for lock in locks:
        if float(lock["start_x"]) <= world_x < float(lock["end_x"]):
            return lock
    return None


def _clipped_runways(
    geometry_plan: dict[str, Any],
    start_x: float,
    end_x: float,
) -> list[dict[str, float]]:
    result: list[dict[str, float]] = []
    for runway in geometry_plan["surface_plan"]["runway_intervals"]:
        clipped_start = max(start_x, float(runway["start_x"]))
        clipped_end = min(end_x, float(runway["end_x"]))
        if clipped_end - clipped_start < MIN_SEGMENT_LENGTH:
            continue
        result.append({
            "start_x": clipped_start,
            "end_x": clipped_end,
            "surface_y": float(runway["surface_y"]),
        })
    return result


def build_spatial_score(
    visual_score: dict[str, Any],
    geometry_plan: dict[str, Any],
    start_seconds: float = DEFAULT_START_SECONDS,
    end_seconds: float = DEFAULT_END_SECONDS,
) -> dict[str, Any]:
    if end_seconds <= start_seconds:
        raise ValueError("end_seconds must be greater than start_seconds")

    gate = visual_score["playability_gate"]
    run_speed = float(gate["controller"]["run_speed"])
    max_step_height = float(gate["controller"]["max_traversable_step_height"])
    max_design_step = float(gate["design_limits"]["max_passive_step_height"])
    if MAX_PASSIVE_DELTA_Y * 2.0 > max_design_step + 1e-9:
        raise ValueError("passive spatial amplitude exceeds visual-score design limit")
    if max_design_step >= max_step_height:
        raise ValueError("passive step design limit must remain below controller step limit")

    start_x = start_seconds * run_speed
    end_x = end_seconds * run_speed
    locks = _action_locks(visual_score, start_seconds, end_seconds)
    runways = _clipped_runways(geometry_plan, start_x, end_x)
    windows = visual_score["windows"]

    segments: list[dict[str, Any]] = []
    for runway in runways:
        boundaries = {float(runway["start_x"]), float(runway["end_x"])}

        for window in windows:
            window_start_x = float(window["start"]) * run_speed
            window_end_x = float(window["end"]) * run_speed
            if runway["start_x"] < window_start_x < runway["end_x"]:
                boundaries.add(window_start_x)
            if runway["start_x"] < window_end_x < runway["end_x"]:
                boundaries.add(window_end_x)

            phase_count = max(1, int(window["beat_span"]["count"]))
            for phase_index in range(1, phase_count):
                phase_x = window_start_x + (window_end_x - window_start_x) * phase_index / phase_count
                if runway["start_x"] < phase_x < runway["end_x"]:
                    boundaries.add(phase_x)

        for lock in locks:
            lock_start_x = float(lock["start_x"])
            lock_end_x = float(lock["end_x"])
            if runway["start_x"] < lock_start_x < runway["end_x"]:
                boundaries.add(lock_start_x)
            if runway["start_x"] < lock_end_x < runway["end_x"]:
                boundaries.add(lock_end_x)

        ordered = sorted(boundaries)
        for left, right in zip(ordered, ordered[1:]):
            if right - left < MIN_SEGMENT_LENGTH:
                continue
            midpoint_x = (left + right) * 0.5
            midpoint_time = midpoint_x / run_speed
            window_index, window = _window_for_time(windows, midpoint_time)
            phase_index, phase_count = _phase_index(window, midpoint_time)
            active_lock = _lock_at_x(locks, midpoint_x)
            locked = active_lock is not None
            delta_y = 0.0 if locked else _passive_delta(window, phase_index, phase_count)
            surface_y = float(runway["surface_y"]) + delta_y
            intent = window["visual_intent"]

            segments.append({
                "start_x": _round(left),
                "end_x": _round(right),
                "length": _round(right - left),
                "base_surface_y": _round(runway["surface_y"]),
                "surface_y": _round(surface_y),
                "delta_y": _round(delta_y),
                "pattern": "ACTION_LOCK" if locked else ROLE_TO_PATTERN[str(intent["phrase_role"])],
                "source_window_index": window_index,
                "source_phase_index": phase_index,
                "source_phase_count": phase_count,
                "source_time": {
                    "start": _round(left / run_speed),
                    "end": _round(right / run_speed),
                },
                "musical_intent": {
                    "phrase_role": intent["phrase_role"],
                    "articulation": intent["articulation"],
                    "contour": intent["contour"],
                    "intensity": intent["intensity"],
                    "continuity": intent["continuity"],
                    "lift": intent["lift"],
                },
                "interaction_lock": None if active_lock is None else {
                    "time": active_lock["time"],
                    "action": active_lock["action"],
                },
            })

    return {
        "schema_version": SCHEMA_VERSION,
        "source_visual_score": "data/music/graceful_opening.visual_score_v0_1.json",
        "source_geometry_plan": (
            "data/geometry/graceful_opening_00_"
            f"{int(round(float(geometry_plan['compiled_time_range']['end']))):02d}"
            ".geometry_plan_v0_1.json"
        ),
        "time_range": {
            "start": _round(start_seconds),
            "end": _round(end_seconds),
        },
        "world_range": {
            "start_x": _round(start_x),
            "end_x": _round(end_x),
        },
        "policy": {
            "type": "passive_spatial_expression_over_existing_runways",
            "event_geometry_preserved": True,
            "new_required_actions": False,
            "new_gaps": False,
            "max_passive_delta_y": MAX_PASSIVE_DELTA_Y,
            "max_adjacent_passive_step": _round(MAX_PASSIVE_DELTA_Y * 2.0),
            "controller_max_traversable_step_height": max_step_height,
            "reaction_lead_seconds": float(gate["design_limits"]["reaction_lead_seconds"]),
            "geometry_lock_actions": sorted(GEOMETRY_LOCK_ACTIONS),
            "beat_subdivision": True,
        },
        "action_locks": locks,
        "segments": segments,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("visual_score", type=Path)
    parser.add_argument("geometry_plan", type=Path)
    parser.add_argument("--start-seconds", type=float, default=DEFAULT_START_SECONDS)
    parser.add_argument("--end-seconds", type=float, default=DEFAULT_END_SECONDS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    visual_score = json.loads(args.visual_score.read_text(encoding="utf-8"))
    geometry_plan = json.loads(args.geometry_plan.read_text(encoding="utf-8"))
    output = build_spatial_score(
        visual_score,
        geometry_plan,
        start_seconds=args.start_seconds,
        end_seconds=args.end_seconds,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
