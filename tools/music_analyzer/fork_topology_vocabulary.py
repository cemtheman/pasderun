#!/usr/bin/env python3
"""Fork Topology Vocabulary v1 for music-derived Pas de Run routes."""

from __future__ import annotations

from typing import Any


SOAR = "SOAR"
TERRACE = "TERRACE"
BRIDGE = "BRIDGE"
CREST = "CREST"
CRESCENDO_STAIRCASE = "CRESCENDO_STAIRCASE"

MAJOR_CLIMAX_MINIMUM = 0.93
CRESCENDO_MINIMUM_DELTA = 0.08
CREST_MINIMUM_CLIMAX = 0.98
CREST_MINIMUM_RISE_DELTA = 0.15

TIER_CONTRACT = {
    "SAFE": {
        "required": True,
        "purpose": "flow-preserving lower-risk choreography",
    },
    "TECHNICAL": {
        "required": False,
        "purpose": "optional precision route with richer choreography",
        "failure_policy": "FAIL_DOWN_TO_SAFE",
    },
    "VIRTUOSO": {
        "required": False,
        "purpose": "future mastery tier for compound aerial choreography",
        "failure_policy": "FAIL_DOWN_TO_TECHNICAL_OR_SAFE",
    },
}


def previous_contiguous_window(
    visual_score: dict[str, Any],
    window_index: int,
) -> dict[str, Any] | None:
    if window_index <= 0:
        return None
    current = visual_score["windows"][window_index]
    previous = visual_score["windows"][window_index - 1]
    if abs(float(previous["end"]) - float(current["start"])) > 0.01:
        return None
    return previous


def classify_topology(
    visual_score: dict[str, Any],
    anchor: dict[str, Any],
) -> str | None:
    interaction = anchor["interaction"]
    if not bool(interaction["required"]) or interaction["candidate_action"] != "JUMP":
        return None

    window_index = int(anchor["window_index"])
    window = visual_score["windows"][window_index]
    if window["visual_intent"]["phrase_role"] != "CLIMAX":
        return None
    if float(window["metrics"]["climax_peak"]) < MAJOR_CLIMAX_MINIMUM:
        return None

    previous = previous_contiguous_window(visual_score, window_index)
    if (
        previous is not None
        and previous["visual_intent"]["phrase_role"] == "BUILD"
        and float(previous["metrics"]["energy_delta"]) >= CRESCENDO_MINIMUM_DELTA
    ):
        return CRESCENDO_STAIRCASE

    next_window = None
    if window_index + 1 < len(visual_score["windows"]):
        candidate = visual_score["windows"][window_index + 1]
        if abs(float(window["end"]) - float(candidate["start"])) <= 0.01:
            next_window = candidate

    if (
        float(window["metrics"]["climax_peak"]) >= CREST_MINIMUM_CLIMAX
        and window["visual_intent"]["contour"] == "RISE"
        and float(window["metrics"]["energy_delta"]) >= CREST_MINIMUM_RISE_DELTA
        and next_window is not None
        and next_window["visual_intent"]["phrase_role"] == "RELEASE"
        and next_window["visual_intent"]["contour"] == "FALL"
    ):
        return CREST

    return SOAR
