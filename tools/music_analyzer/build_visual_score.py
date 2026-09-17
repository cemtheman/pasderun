#!/usr/bin/env python3
"""Build a continuous visual score with an explicit player-load playability gate."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
BEATS_PER_WINDOW = 4

RUN_SPEED = 4.0
JUMP_VELOCITY = 6.0
GRAVITY = 18.0
LOW_TRANSITION_DURATION = 0.55
MAX_TRAVERSABLE_STEP_HEIGHT = 0.45
MAX_CALIBRATED_GAP = 2.2

REACTION_LEAD_SECONDS = 0.75
MIN_REQUIRED_ACTION_SPACING_SECONDS = 0.90
MAX_REQUIRED_ACTIONS_PER_WINDOW = 1
MAX_PASSIVE_STEP_HEIGHT = 0.30
LOW_PASSAGE_MAX_LENGTH = 1.80

ACTION_OCCUPANCY_SECONDS = {
    "JUMP": 2.0 * JUMP_VELOCITY / GRAVITY + 0.25,
    "SWIPE_DOWN": LOW_TRANSITION_DURATION + 0.25,
    "HOLD": 1.00,
    "TAP": 0.30,
}

CLASS_TO_ACTION = {
    "SMALL_JUMP": "JUMP",
    "MEDIUM_JUMP": "JUMP",
    "LARGE_TRAVELLING_LEAP": "JUMP",
    "SUSTAINED_BALANCE": "HOLD",
    "CONTROLLED_TRANSITION": "SWIPE_DOWN",
    "ACCENT_ACTION": "TAP",
}


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _round(value: float) -> float:
    return round(float(value), 4)


def _mean(points: list[dict[str, Any]], start: float, end: float, key: str = "value") -> float:
    values = [float(point[key]) for point in points if start <= float(point["time"]) < end]
    if values:
        return sum(values) / len(values)
    midpoint = (start + end) * 0.5
    nearest = min(points, key=lambda point: abs(float(point["time"]) - midpoint))
    return float(nearest[key])


def _peak(events: list[dict[str, Any]], start: float, end: float) -> tuple[float, float | None]:
    candidates = [
        (float(event["strength"]), float(event["time"]))
        for event in events
        if start <= float(event["time"]) < end
    ]
    if not candidates:
        return 0.0, None
    strength, time = max(candidates, key=lambda item: (item[0], -item[1]))
    return strength, time


def _window_bounds(beats: list[float], duration: float) -> list[tuple[float, float, int, int]]:
    if len(beats) < 2:
        raise ValueError("visual score requires at least two detected beats")

    boundaries = [0.0]
    beat_indices = [0]
    index = BEATS_PER_WINDOW
    while index < len(beats):
        boundaries.append(float(beats[index]))
        beat_indices.append(index)
        index += BEATS_PER_WINDOW
    if boundaries[-1] < duration:
        boundaries.append(duration)
        beat_indices.append(len(beats))

    windows: list[tuple[float, float, int, int]] = []
    for idx in range(len(boundaries) - 1):
        start = boundaries[idx]
        end = boundaries[idx + 1]
        if end - start <= 0.05:
            continue
        windows.append((start, end, beat_indices[idx], beat_indices[idx + 1]))
    return windows


def _phrase_role(
    energy_delta: float,
    density: float,
    sustain: float,
    boundary: float,
    climax: float,
) -> str:
    if climax >= 0.80:
        return "CLIMAX"
    if boundary >= 0.55:
        return "TURNING_POINT"
    if sustain >= 0.60 and density < 0.58:
        return "SUSTAIN"
    if energy_delta >= 0.08:
        return "BUILD"
    if energy_delta <= -0.08:
        return "RELEASE"
    if density >= 0.70:
        return "PULSE"
    return "FLOW"


def _articulation(density: float, sustain: float, accent: float) -> str:
    if sustain >= 0.62 and density < 0.62:
        return "LEGATO"
    if accent >= 0.78:
        return "ACCENTED"
    if density >= 0.72:
        return "PULSED"
    return "MIXED"


def _contour(energy_delta: float) -> str:
    if energy_delta >= 0.06:
        return "RISE"
    if energy_delta <= -0.06:
        return "FALL"
    return "LEVEL"


def _event_anchors(movement_demands: dict[str, Any]) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    last_required_time = -math.inf
    last_required_end = -math.inf

    for event in movement_demands["events"]:
        candidates = event["candidate_classes"]
        primary_class = String = str(candidates[0]["class"])
        action = CLASS_TO_ACTION.get(primary_class)
        time = float(event["time"])

        required = action is not None
        suppression_reason: str | None = None
        occupancy = ACTION_OCCUPANCY_SECONDS.get(action, 0.0) if action else 0.0

        if required:
            if time - last_required_time < MIN_REQUIRED_ACTION_SPACING_SECONDS:
                required = False
                suppression_reason = "required_action_spacing"
            elif time < last_required_end:
                required = False
                suppression_reason = "required_action_overlap"

        if required:
            last_required_time = time
            last_required_end = time + occupancy

        anchors.append({
            "time": round(time, 3),
            "primary_class": primary_class,
            "confidence": float(candidates[0]["confidence"]),
            "interaction": {
                "candidate_action": action,
                "required": required,
                "occupancy_seconds": _round(occupancy),
                "suppression_reason": suppression_reason,
            },
            "branchability": float(event["branchability"]),
        })

    return anchors


def build_visual_score(analysis: dict[str, Any], movement_demands: dict[str, Any]) -> dict[str, Any]:
    duration = float(analysis["source"]["duration_seconds"])
    beats = [float(value) for value in analysis["tempo"]["beats"]]
    sustain_points = analysis["sustain"]["points"]

    windows: list[dict[str, Any]] = []
    for start, end, beat_start, beat_end in _window_bounds(beats, duration):
        energy = _mean(analysis["energy"], start, end)
        energy_delta = _mean(analysis["energy"], start, end, "delta")
        density = _mean(analysis["rhythmic_density"], start, end)
        sustain = _mean(sustain_points, start, end)
        accent, accent_time = _peak(analysis["accents"], start, end)
        boundary, boundary_time = _peak(analysis["boundaries"], start, end)
        climax, climax_time = _peak(analysis["climax_candidates"], start, end)

        intensity = _clamp(
            0.30 * energy
            + 0.30 * density
            + 0.20 * accent
            + 0.20 * climax
        )
        continuity = _clamp(0.65 * sustain + 0.35 * (1.0 - density))
        lift = _clamp(
            0.45 * climax
            + 0.30 * max(energy_delta, 0.0)
            + 0.25 * accent
        )

        windows.append({
            "start": _round(start),
            "end": _round(end),
            "duration": _round(end - start),
            "beat_span": {
                "start_index": beat_start,
                "end_index": beat_end,
                "count": max(0, beat_end - beat_start),
            },
            "metrics": {
                "energy": _round(energy),
                "energy_delta": _round(energy_delta),
                "rhythmic_density": _round(density),
                "sustain": _round(sustain),
                "accent_peak": _round(accent),
                "boundary_peak": _round(boundary),
                "climax_peak": _round(climax),
            },
            "salient_times": {
                "accent": None if accent_time is None else _round(accent_time),
                "boundary": None if boundary_time is None else _round(boundary_time),
                "climax": None if climax_time is None else _round(climax_time),
            },
            "visual_intent": {
                "phrase_role": _phrase_role(energy_delta, density, sustain, boundary, climax),
                "articulation": _articulation(density, sustain, accent),
                "contour": _contour(energy_delta),
                "intensity": _round(intensity),
                "continuity": _round(continuity),
                "lift": _round(lift),
            },
            "interaction_budget": {
                "max_required_actions": MAX_REQUIRED_ACTIONS_PER_WINDOW,
                "passive_spatial_change": True,
            },
        })

    jump_airtime = 2.0 * JUMP_VELOCITY / GRAVITY
    jump_range = jump_airtime * RUN_SPEED

    return {
        "schema_version": SCHEMA_VERSION,
        "source_analysis": analysis["source"]["file"],
        "source_movement_demands": movement_demands["source_analysis"],
        "duration_seconds": duration,
        "method": {
            "type": "continuous_visual_score_with_playability_gate",
            "beats_per_window": BEATS_PER_WINDOW,
            "principle": "music may vary continuously; required player input remains sparse and physically feasible",
        },
        "playability_gate": {
            "controller": {
                "run_speed": RUN_SPEED,
                "jump_velocity": JUMP_VELOCITY,
                "gravity": GRAVITY,
                "jump_airtime_seconds": _round(jump_airtime),
                "same_height_jump_range_world": _round(jump_range),
                "low_transition_duration_seconds": LOW_TRANSITION_DURATION,
                "low_transition_distance_world": _round(LOW_TRANSITION_DURATION * RUN_SPEED),
                "max_traversable_step_height": MAX_TRAVERSABLE_STEP_HEIGHT,
            },
            "design_limits": {
                "reaction_lead_seconds": REACTION_LEAD_SECONDS,
                "min_required_action_spacing_seconds": MIN_REQUIRED_ACTION_SPACING_SECONDS,
                "max_required_actions_per_window": MAX_REQUIRED_ACTIONS_PER_WINDOW,
                "max_passive_step_height": MAX_PASSIVE_STEP_HEIGHT,
                "max_gap_world": MAX_CALIBRATED_GAP,
                "low_passage_max_length_world": LOW_PASSAGE_MAX_LENGTH,
                "required_input_concurrency": 1,
            },
            "action_occupancy_seconds": {
                key: _round(value) for key, value in ACTION_OCCUPANCY_SECONDS.items()
            },
        },
        "windows": windows,
        "event_anchors": _event_anchors(movement_demands),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("movement_demands", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    movement_demands = json.loads(args.movement_demands.read_text(encoding="utf-8"))
    output = build_visual_score(analysis, movement_demands)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
