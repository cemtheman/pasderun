"""Measured frontal hand silhouette intervals from deformed final-Rig mesh points."""

from __future__ import annotations

from schema_validation import require
from static_pose import dot


def frontal_hand_gap(points: dict[str, list[list[float]]], left_axis: list[float]) -> dict:
    """Positive gap separates projected hands; negative gap means lateral overlap.

    A negative 2D gap is not proof of a 3D mesh intersection.
    """
    require(set(points) == {"left", "right"} and all(points[side] for side in points),
            "hand_mesh", "both sides need sampled hand vertices")
    coordinates = {side: [dot(point, left_axis) for point in points[side]]
                   for side in ("left", "right")}
    left_inner = min(coordinates["left"])
    right_inner = max(coordinates["right"])
    return {
        "left_lateral_min": round(left_inner, 8),
        "right_lateral_max": round(right_inner, 8),
        "projected_gap_armature_units": round(left_inner - right_inner, 8),
        "left_vertex_count": len(points["left"]),
        "right_vertex_count": len(points["right"]),
        "meaning": "Positive separates hand silhouettes laterally; negative overlaps in frontal projection only."
    }
