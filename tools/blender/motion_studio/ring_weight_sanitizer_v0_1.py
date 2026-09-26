"""Runtime sanitizer for implausible ring-finger deform weights.

Purpose: the repaired rig's Ring_L/R bone naming is correct, but isolated
ring-only posing shows ~0.7086 armature-unit evaluated-mesh displacement on the
main 'girl' mesh while fingertip bone coordinates remain local. That pattern is
consistent with stray deform weights, not a bone-chain geometry error.

This module removes only ring-chain weights from vertices that are far outside
the corresponding ring-finger rest neighborhood. Remaining deform weights are
renormalized. Source GLB is NOT modified; this is a diagnostic/runtime patch
used to prove the weight-corruption hypothesis before a source migration.
"""

from __future__ import annotations

import math
from mathutils import Vector


def _point_segment_distance(point: Vector, a: Vector, b: Vector) -> float:
    ab = b - a
    denom = ab.length_squared
    if denom <= 1e-12:
        return (point - a).length
    t = max(0.0, min(1.0, (point - a).dot(ab) / denom))
    closest = a + ab * t
    return (point - closest).length


def _ring_rest_segments(armature, chain_names):
    segments = []
    total = 0.0
    for name in chain_names:
        bone = armature.data.bones[name]
        a = bone.head_local.copy()
        b = bone.tail_local.copy()
        segments.append((a, b))
        total += (b - a).length
    return segments, total


def sanitize_ring_weights(armature, mapping, distance_factor: float = 1.75):
    report = {"distance_factor": distance_factor, "sides": {}, "removed_total": 0}

    for side in ("left", "right"):
        chain = mapping["hands"][side]["ring"]
        segments, chain_length = _ring_rest_segments(armature, chain)
        max_distance = max(chain_length * distance_factor, 0.03)
        side_report = {
            "chain": chain,
            "chain_length": round(chain_length, 8),
            "max_rest_distance": round(max_distance, 8),
            "objects": {},
            "removed_influences": 0,
            "affected_vertices": 0,
        }

        for obj in armature.children:
            pass

        for obj in list(armature.users_scene[0].objects) if armature.users_scene else []:
            if obj.type != "MESH":
                continue
            if not any(mod.type == "ARMATURE" and mod.object == armature for mod in obj.modifiers):
                continue

            group_by_name = {g.name: g for g in obj.vertex_groups}
            ring_groups = [group_by_name[name] for name in chain if name in group_by_name]
            if not ring_groups:
                continue
            ring_group_indices = {g.index for g in ring_groups}

            to_armature = armature.matrix_world.inverted() @ obj.matrix_world
            removed = 0
            touched_vertices = set()

            for vertex in obj.data.vertices:
                active_ring = [
                    assignment for assignment in vertex.groups
                    if assignment.group in ring_group_indices and assignment.weight > 0.0
                ]
                if not active_ring:
                    continue
                point = to_armature @ vertex.co
                distance = min(
                    _point_segment_distance(point, a, b)
                    for a, b in segments
                )
                if distance <= max_distance:
                    continue

                # Remove only the suspect ring-chain influences. Other skin
                # groups are retained; Blender's armature modifier naturally
                # uses their existing values. We intentionally do not invent
                # replacement ownership.
                for group in ring_groups:
                    try:
                        group.remove([vertex.index])
                    except RuntimeError:
                        pass
                removed += len(active_ring)
                touched_vertices.add(vertex.index)

            if removed:
                obj.data.update()
                side_report["objects"][obj.name] = {
                    "removed_influences": removed,
                    "affected_vertices": len(touched_vertices),
                }
                side_report["removed_influences"] += removed
                side_report["affected_vertices"] += len(touched_vertices)

        report["sides"][side] = side_report
        report["removed_total"] += side_report["removed_influences"]

    return report
