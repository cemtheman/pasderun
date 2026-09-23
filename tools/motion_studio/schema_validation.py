"""Small dependency-free validator for the JSON Schema keywords used here."""

from __future__ import annotations

import json
import math
import re

from validate import ContractError


def require(condition: bool, where: str, message: str) -> None:
    if not condition:
        raise ContractError(f"{where}: {message}")


def shape(value: object, rule: dict, where: str, definitions: dict) -> None:
    if "$ref" in rule:
        require(rule["$ref"].startswith("#/$defs/"), where, "unsupported reference")
        return shape(value, definitions[rule["$ref"].split("/")[-1]], where, definitions)
    if "const" in rule:
        require(type(value) is type(rule["const"]) and value == rule["const"], where, "wrong constant")
    if "enum" in rule:
        require(value in rule["enum"], where, "unknown value")
    kind = rule.get("type")
    if kind == "object":
        require(isinstance(value, dict), where, "expected object")
        require(all(key in value for key in rule.get("required", [])), where, "missing field")
        require(len(value) >= rule.get("minProperties", 0), where, "too few properties")
        for key, item in value.items():
            child = rule.get("properties", {}).get(key, rule.get("additionalProperties", True))
            require(child is not False, f"{where}.{key}", "unknown field")
            if isinstance(child, dict):
                shape(item, child, f"{where}.{key}", definitions)
    elif kind == "array":
        require(isinstance(value, list), where, "expected array")
        require(rule.get("minItems", 0) <= len(value) <= rule.get("maxItems", math.inf), where, "invalid array length")
        if rule.get("uniqueItems"):
            require(len({json.dumps(x, sort_keys=True) for x in value}) == len(value), where, "duplicate item")
        for index, item in enumerate(value):
            shape(item, rule["items"], f"{where}[{index}]", definitions)
    elif kind == "string":
        require(isinstance(value, str) and len(value) >= rule.get("minLength", 0), where, "invalid string")
        if "pattern" in rule:
            require(re.fullmatch(rule["pattern"], value) is not None, where, "invalid format")
    elif kind == "number":
        require(type(value) in (int, float) and math.isfinite(value), where, "expected finite number")
        if "minimum" in rule:
            require(value >= rule["minimum"], where, "below minimum")
        if "maximum" in rule:
            require(value <= rule["maximum"], where, "above maximum")
        if "exclusiveMinimum" in rule:
            require(value > rule["exclusiveMinimum"], where, "below exclusive minimum")
    elif kind == "integer":
        require(type(value) is int, where, "expected integer")
        if "minimum" in rule:
            require(value >= rule["minimum"], where, "below minimum")
    elif kind == "boolean":
        require(type(value) is bool, where, "expected boolean")
    elif isinstance(kind, list):
        require(kind == ["string", "null"] and (value is None or isinstance(value, str)), where, "invalid nullable string")
