"""Contact plane alignment and support polygon from explicit foot patches."""

from __future__ import annotations

import json
import math
from pathlib import Path

from schema_validation import require, shape
from rig_calibration import frame_valid


SCHEMA = json.loads(Path(__file__).with_name("contact_support_v0_4.schema.json").read_text(encoding="utf-8"))


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross2(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def hull(points):
    """Monotone chain, CCW, without duplicate or collinear interior points."""
    unique = sorted(set(points))
    require(len(unique) >= 3, "support", "fewer than three distinct projected points")
    lower = []
    for point in unique:
        while len(lower) >= 2 and cross2(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross2(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    outline = lower[:-1] + upper[:-1]
    require(len(outline) >= 3, "support", "collinear contact patch")
    area = sum(outline[i][0]*outline[(i+1) % len(outline)][1] -
               outline[(i+1) % len(outline)][0]*outline[i][1]
               for i in range(len(outline))) * 0.5
    require(area > 1e-10, "support", "degenerate support polygon")
    return outline, area


def signed_edge_margin(outline, point):
    return min(cross2(a, b, point) / math.dist(a, b)
               for a, b in zip(outline, outline[1:] + outline[:1]))


def solve_contact_support(spec, calibration=None):
    shape(spec, SCHEMA, "contact_support", SCHEMA["$defs"])
    frame_valid(spec["anatomical_frame"])
    if calibration is not None:
        require(spec["rig_profile_id"] == calibration["rig_profile_id"], "support", "rig profile mismatch")
        require(spec["source_glb_sha256"] == calibration["source"]["sha256"], "support", "GLB digest mismatch")
        require(spec["anatomical_frame"] == calibration["anatomical_frame"], "support", "anatomical frame mismatch")
    patches = spec["patches"]
    by_id = {p["id"]: p for p in patches}
    require(len(by_id) == len(patches), "patches", "duplicate patch id")
    require(set(spec["active_patch_ids"]).issubset(by_id), "support", "unknown active patch")
    frame = spec["anatomical_frame"]
    points = []
    projected = []
    for patch_id in spec["active_patch_ids"]:
        patch = by_id[patch_id]
        patch_2d = []
        for point in patch["points"]:
            position = point["position_armature_local"]
            coords = (dot(position, frame["left"]), dot(position, frame["front"]))
            patch_2d.append(coords)
            projected.append(coords)
            points.append(dot(position, frame["up"]))
        hull(patch_2d)
    outline, area = hull(projected)
    spread = max(points) - min(points)
    require(spread <= spec["max_contact_height_spread"], "contact", "active patches cannot share one ground plane")
    vertical_shift = spec["ground_height_up"] - min(points)
    result = {
        "pose_id": spec["pose_id"], "active_patch_ids": spec["active_patch_ids"],
        "root_shift_up": vertical_shift, "contact_height_spread": spread,
        "support_polygon_left_front": [list(x) for x in outline], "support_area": area,
        "balance_status": "UNKNOWN_NO_COM",
    }
    if "center_of_mass" in spec:
        com = spec["center_of_mass"]
        position = com["position_armature_local"]
        projection = (dot(position, frame["left"]), dot(position, frame["front"]))
        margin = signed_edge_margin(outline, projection)
        result["center_of_mass_projection_left_front"] = list(projection)
        result["signed_edge_margin"] = margin
        source_kind = com["source"]["kind"]
        result["balance_status"] = (
            "INDICATIVE_ESTIMATE" if source_kind == "human_estimate" else
            "INSIDE_SUPPORT" if margin >= 0 else "OUTSIDE_SUPPORT"
        )
    return result
