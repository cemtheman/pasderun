#!/usr/bin/env python3
"""Deterministic, explainable music-to-movement demand inference prototype."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
CONTEXT_SECONDS = 2.5
EVENT_RADIUS_SECONDS = 0.5
SEED_MERGE_SECONDS = 1.25
ACCENT_SEED_MINIMUM = 0.72
CLASS_CONFIDENCE_MINIMUM = 0.34
MAX_CLASSES_PER_EVENT = 9

MOVEMENT_CLASSES = (
    "TRAVEL",
    "ACCENT_ACTION",
    "SMALL_JUMP",
    "MEDIUM_JUMP",
    "LARGE_TRAVELLING_LEAP",
    "SUSTAINED_BALANCE",
    "TURN",
    "CONTROLLED_TRANSITION",
    "RECOVERY",
)

def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def _round(value: float) -> float:
    return round(_clamp(value), 4)


def _mean_in_range(points: list[dict[str, float]], start: float, end: float, key: str = "value") -> float:
    values = [float(point[key]) for point in points if start <= float(point["time"]) <= end]
    if values:
        return sum(values) / len(values)
    nearest = min(points, key=lambda point: abs(float(point["time"]) - (start + end) / 2.0))
    return float(nearest[key])


def _max_near(events: list[dict[str, float]], time: float, radius: float) -> float:
    return max(
        (float(event["strength"]) for event in events if abs(float(event["time"]) - time) <= radius),
        default=0.0,
    )


def _seed_events(analysis: dict[str, Any]) -> list[float]:
    seeds: list[tuple[float, float]] = []
    seeds.extend(
        (float(item["time"]), 1.1 * float(item["strength"]))
        for item in analysis["climax_candidates"]
    )
    seeds.extend(
        (float(item["time"]), 0.9 * float(item["strength"]))
        for item in analysis["boundaries"]
    )
    seeds.extend(
        (float(item["time"]), float(item["strength"]))
        for item in analysis["accents"]
        if float(item["strength"]) >= ACCENT_SEED_MINIMUM
    )
    seeds.sort()

    groups: list[list[tuple[float, float]]] = []
    for seed in seeds:
        if not groups or seed[0] - groups[-1][-1][0] > SEED_MERGE_SECONDS:
            groups.append([seed])
        else:
            groups[-1].append(seed)
    return [max(group, key=lambda item: (item[1], -item[0]))[0] for group in groups]


def _musical_context(analysis: dict[str, Any], time: float) -> tuple[dict[str, float], dict[str, float]]:
    energy = analysis["energy"]
    density = analysis["rhythmic_density"]
    sustain = analysis["sustain"]["points"]
    pre_start, pre_end = time - CONTEXT_SECONDS, time - EVENT_RADIUS_SECONDS
    post_start, post_end = time + EVENT_RADIUS_SECONDS, time + CONTEXT_SECONDS
    event_start, event_end = time - EVENT_RADIUS_SECONDS, time + EVENT_RADIUS_SECONDS

    pre_energy = _mean_in_range(energy, pre_start, pre_end)
    post_energy = _mean_in_range(energy, post_start, post_end)
    context = {
        "accent_strength": _max_near(analysis["accents"], time, EVENT_RADIUS_SECONDS),
        "energy": _mean_in_range(energy, event_start, event_end),
        "energy_delta": _mean_in_range(energy, event_start, event_end, "delta"),
        "rhythmic_density": _mean_in_range(density, event_start, event_end),
        "sustain": _mean_in_range(sustain, event_start, event_end),
        "climax_strength": _max_near(analysis["climax_candidates"], time, 0.75),
        "boundary_strength": _max_near(analysis["boundaries"], time, 0.75),
    }
    temporal = {
        "pre_energy": pre_energy,
        "post_energy": post_energy,
        "energy_trend": post_energy - pre_energy,
        "preparation_space": _clamp((time - max(0.0, pre_start)) / CONTEXT_SECONDS),
        "recovery_space": _clamp((float(analysis["source"]["duration_seconds"]) - time) / CONTEXT_SECONDS),
    }
    return ({key: round(value, 4) for key, value in context.items()}, temporal)


def _movement_demand(context: dict[str, float], temporal: dict[str, float]) -> dict[str, float]:
    accent = context["accent_strength"]
    energy = context["energy"]
    density = context["rhythmic_density"]
    stable = context["sustain"]
    climax = context["climax_strength"]
    boundary = context["boundary_strength"]
    positive_change = _clamp(max(context["energy_delta"], temporal["energy_trend"]) * 2.0)
    attack = max(accent, density)

    travel = 0.25 * energy + 0.25 * density + 0.25 * climax + 0.15 * positive_change + 0.10 * boundary
    verticality = 0.35 * accent + 0.25 * positive_change + 0.25 * climax + 0.15 * density
    sustain_demand = 0.65 * stable + 0.20 * energy + 0.15 * (1.0 - density)
    balance = 0.60 * stable + 0.25 * (1.0 - attack) + 0.15 * (1.0 - min(1.0, abs(temporal["energy_trend"]) * 2.0))
    technicality = 0.30 * density + 0.25 * accent + 0.25 * climax + 0.20 * attack
    rotation = 0.45 * density + 0.25 * accent + 0.20 * technicality + 0.10 * boundary
    movement_scale = 0.30 * energy + 0.25 * verticality + 0.25 * climax + 0.20 * travel
    return {
        "travel": _round(travel),
        "verticality": _round(verticality),
        "sustain": _round(sustain_demand),
        "balance": _round(balance),
        "rotation": _round(rotation),
        "movement_scale": _round(movement_scale),
        "technicality": _round(technicality),
    }


def _closeness(value: float, center: float, width: float) -> float:
    return _clamp(1.0 - abs(value - center) / width)


def _class_scores(context: dict[str, float], temporal: dict[str, float], demand: dict[str, float]) -> dict[str, float]:
    accent = context["accent_strength"]
    density = context["rhythmic_density"]
    boundary = context["boundary_strength"]
    climax = context["climax_strength"]
    falling = _clamp(-temporal["energy_trend"] * 2.5)
    rising = _clamp(temporal["energy_trend"] * 2.5)
    scale = demand["movement_scale"]
    vertical = demand["verticality"]
    preparation = temporal["preparation_space"]
    recovery = temporal["recovery_space"]

    scores = {
        "TRAVEL": 0.70 * demand["travel"] + 0.20 * demand["movement_scale"] + 0.10 * density,
        "ACCENT_ACTION": 0.65 * accent + 0.20 * density + 0.15 * (1.0 - context["sustain"]),
        "SMALL_JUMP": 0.35 * vertical + 0.35 * _closeness(scale, 0.34, 0.30) + 0.20 * accent + 0.10 * preparation,
        "MEDIUM_JUMP": 0.35 * vertical + 0.35 * _closeness(scale, 0.58, 0.34) + 0.15 * demand["technicality"] + 0.15 * preparation,
        "LARGE_TRAVELLING_LEAP": (
            0.22 * demand["travel"] + 0.22 * vertical + 0.22 * scale + 0.20 * climax
            + 0.07 * preparation + 0.07 * recovery
        ),
        "SUSTAINED_BALANCE": 0.52 * demand["balance"] + 0.33 * demand["sustain"] + 0.15 * (1.0 - density),
        "TURN": 0.55 * demand["rotation"] + 0.30 * demand["technicality"] + 0.15 * density,
        "CONTROLLED_TRANSITION": 0.40 * demand["sustain"] + 0.25 * boundary + 0.20 * (1.0 - accent) + 0.15 * max(rising, falling),
        "RECOVERY": 0.45 * falling + 0.25 * (1.0 - density) + 0.15 * boundary + 0.15 * (1.0 - accent),
    }
    return {key: _round(value) for key, value in scores.items()}


def _explanation(context: dict[str, float], temporal: dict[str, float], classes: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    if context["climax_strength"] >= 0.7:
        reasons.append("strong climax candidate")
    if context["accent_strength"] >= 0.7:
        reasons.append("strong local attack accent")
    if context["rhythmic_density"] >= 0.6:
        reasons.append("high local onset density")
    if context["sustain"] >= 0.65:
        reasons.append("stable, low-attack sustain proxy")
    if temporal["energy_trend"] >= 0.08 or context["energy_delta"] >= 0.08:
        reasons.append("positive energy change")
    if temporal["energy_trend"] <= -0.08 or context["energy_delta"] <= -0.08:
        reasons.append("falling energy supports release or recovery")
    if context["boundary_strength"] >= 0.5:
        reasons.append("strong structural-boundary candidate")
    if any(item["class"] == "LARGE_TRAVELLING_LEAP" for item in classes):
        reasons.append("travel, verticality, scale, and temporal preparation jointly support a broad leap demand")
    if not reasons:
        reasons.append("combined moderate musical context")
    return reasons


def infer_movements(analysis: dict[str, Any]) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    duration = float(analysis["source"]["duration_seconds"])
    for time in _seed_events(analysis):
        context, temporal = _musical_context(analysis, time)
        demand = _movement_demand(context, temporal)
        scores = _class_scores(context, temporal, demand)
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        candidates = [
            {"class": movement_class, "confidence": confidence}
            for movement_class, confidence in ranked
            if confidence >= CLASS_CONFIDENCE_MINIMUM
        ][:MAX_CLASSES_PER_EVENT]
        if not candidates:
            candidates = [{"class": ranked[0][0], "confidence": ranked[0][1]}]
        competitive = sum(1 for item in candidates if item["confidence"] >= candidates[0]["confidence"] - 0.12)
        phrase_space = min(temporal["preparation_space"], temporal["recovery_space"])
        branchability = _round(0.60 * _clamp((competitive - 1) / 3.0) + 0.40 * phrase_space)
        events.append({
            "time": round(time, 3),
            "window_start": round(max(0.0, time - CONTEXT_SECONDS), 3),
            "window_end": round(min(duration, time + CONTEXT_SECONDS), 3),
            "musical_context": context,
            "movement_demand": demand,
            "candidate_classes": candidates,
            "branchability": branchability,
            "explanation": _explanation(context, temporal, candidates),
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "source_analysis": analysis["source"]["file"],
        "source_analysis_schema_version": analysis["schema_version"],
        "duration_seconds": duration,
        "method": {
            "type": "deterministic_explainable_heuristic",
            "context_seconds": CONTEXT_SECONDS,
            "event_seed_policy": "climax and boundary candidates plus accents at or above 0.72, merged within 1.25 seconds",
            "limitations": "No model training or classical-audio similarity is claimed. Classical choreography data supplies vocabulary and sanity anchors only.",
        },
        "movement_classes": list(MOVEMENT_CLASSES),
        "events": events,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    output = infer_movements(analysis)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
