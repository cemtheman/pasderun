"""Motion Studio v0 contract validation; standard library only, no solver."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path


SCHEMA = json.loads(Path(__file__).with_name("contracts_v0.schema.json").read_text(encoding="utf-8"))
DEFS = SCHEMA["$defs"]
FOOT_LANDMARKS = {f"{side}_{part}" for side in ("left", "right") for part in ("ankle", "heel", "toe")}


class ContractError(ValueError):
    pass


def _require(ok: bool, where: str, message: str) -> None:
    if not ok:
        raise ContractError(f"{where}: {message}")


def _shape(value: object, schema: dict, where: str) -> None:
    """Evaluate only the JSON Schema keywords used in this versioned contract."""
    if "$ref" in schema:
        _require(schema["$ref"].startswith("#/$defs/"), where, "unsupported reference")
        return _shape(value, DEFS[schema["$ref"].split("/")[-1]], where)
    if "const" in schema:
        _require(value == schema["const"], where, f"expected {schema['const']!r}")
    if "enum" in schema:
        _require(value in schema["enum"], where, "unknown value")
    kind = schema.get("type")
    if kind == "object":
        _require(isinstance(value, dict), where, "expected object")
        for key in schema.get("required", []):
            _require(key in value, where, f"missing {key}")
        _require(len(value) >= schema.get("minProperties", 0), where, "too few properties")
        props = schema.get("properties", {})
        for key, item in value.items():
            rule = props.get(key, schema.get("additionalProperties", True))
            _require(rule is not False, f"{where}.{key}", "unknown property")
            if isinstance(rule, dict):
                _shape(item, rule, f"{where}.{key}")
    elif kind == "array":
        _require(isinstance(value, list), where, "expected array")
        _require(len(value) >= schema.get("minItems", 0), where, "too few items")
        _require(len(value) <= schema.get("maxItems", math.inf), where, "too many items")
        if schema.get("uniqueItems"):
            _require(len({json.dumps(v, sort_keys=True) for v in value}) == len(value), where, "duplicate item")
        for n, item in enumerate(value):
            prefix = schema.get("prefixItems", [])
            rule = prefix[n] if n < len(prefix) else schema.get("items")
            if rule:
                _shape(item, rule, f"{where}[{n}]")
    elif kind == "integer":
        _require(type(value) is int, where, "expected integer")
    elif kind == "number":
        _require(type(value) in (int, float) and math.isfinite(value), where, "expected finite number")
    elif kind == "string":
        _require(isinstance(value, str), where, "expected string")
        _require(len(value) >= schema.get("minLength", 0), where, "empty string")
        if "pattern" in schema:
            _require(re.fullmatch(schema["pattern"], value) is not None, where, "invalid format")
    if kind in ("integer", "number"):
        _require(value >= schema.get("minimum", -math.inf), where, "below minimum")


def _interval(item: dict, duration: int, where: str) -> None:
    _require(0 <= item["start_frame"] < item["end_frame"] <= duration, where, "invalid half-open frame interval")


def _unique_ids(items: list[dict], where: str) -> None:
    ids = [item["id"] for item in items]
    _require(len(ids) == len(set(ids)), where, "duplicate id")


def validate(kind: str, data: dict) -> dict:
    """Validate JSON shape and cross references; return the input or raise ContractError."""
    _require(kind in ("human_model", "motion_spec", "contact", "support", "rig_profile", "qa_result", "asset_metadata"), "contract", "unknown kind")
    _shape(data, DEFS[kind], kind)

    if kind == "human_model":
        _require(set(data["landmarks"]) == set(DEFS["landmark"]["enum"]), kind, "landmark inventory mismatch")
    elif kind == "motion_spec":
        duration = data["duration_frames"]
        phases = data["phases"]
        _unique_ids(phases, "phases")
        next_frame = 0
        for phase in phases:
            _interval(phase, duration, "phase")
            _require(phase["start_frame"] == next_frame, "phases", "must be contiguous and ordered")
            next_frame = phase["end_frame"]
        _require(next_frame == duration, "phases", "must cover motion duration")
        _unique_ids(data["markers"], "markers")
        frames = [m["frame"] for m in data["markers"]]
        _require(frames == sorted(frames) and all(f < duration for f in frames), "markers", "out of order or out of range")
        _require(all(0 <= t["frame"] < duration for t in data["landmark_targets"]), "landmark_targets", "frame out of range")
        targets = [(t["frame"], t["landmark"]) for t in data["landmark_targets"]]
        _require(len(targets) == len(set(targets)), "landmark_targets", "duplicate target")
        contacts = data["contacts"]
        _unique_ids(contacts, "contacts")
        by_id = {c["id"]: c for c in contacts}
        for c in contacts:
            _interval(c, duration, "contact")
        next_frame = 0
        for s in data["support"]:
            _interval(s, duration, "support")
            _require(s["start_frame"] == next_frame, "support", "must be contiguous and ordered")
            next_frame = s["end_frame"]
            for contact_id in s["contact_ids"]:
                _require(contact_id in by_id, "support", f"unknown contact {contact_id}")
                c = by_id[contact_id]
                _require(c["landmark"] in FOOT_LANDMARKS and c["mode"] in ("planted", "rolling"), "support", "requires load-bearing foot contact")
                _require(c["start_frame"] <= s["start_frame"] and c["end_frame"] >= s["end_frame"], "support", "contact does not span support interval")
        _require(next_frame == duration, "support", "must cover motion duration; use empty contact_ids for flight")
        for c in data["constraints"]:
            _require("phase_id" not in c or c["phase_id"] in {p["id"] for p in phases}, "constraints", "unknown phase")
    elif kind == "rig_profile":
        _require(set(data["landmark_bones"]).issubset(DEFS["landmark"]["enum"]), kind, "unknown landmark")
        axes = data["anatomical_frame"]
        for name in ("up", "left", "front"):
            _require(abs(sum(x*x for x in axes[name]) - 1) < 1e-4, kind, f"{name} must have unit length")
        for a, b in (("up", "left"), ("up", "front"), ("left", "front")):
            _require(abs(sum(x*y for x, y in zip(axes[a], axes[b]))) < 1e-4, kind, "frame axes must be orthogonal")
    elif kind == "qa_result":
        statuses = [check["status"] for check in data["checks"]]
        _require(len({c["name"] for c in data["checks"]}) == len(statuses), kind, "duplicate check")
        if data["status"] == "pass":
            _require(bool(statuses) and all(s == "pass" for s in statuses), kind, "pass requires passing checks")
        elif data["status"] == "fail":
            _require("fail" in statuses, kind, "fail requires failing check")
        else:
            _require(all(s == "not_run" for s in statuses), kind, "not_run cannot contain executed checks")
    elif kind == "asset_metadata":
        _require(data["review_status"] != "approved" or bool(data["reviewers"]), kind, "approval requires reviewer")
    return data
