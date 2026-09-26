"""Anatomy-aware ring deform-weight repair for Motion Studio runtime proof.

The repaired source rig has correct Ring_L/R bone names and hierarchy, but
ring-only posing exposed large skinned-mesh spikes. v0.1 removed only very
distant ring influences; the spikes remained. This v0.2 sanitizer keeps ring
weights only where the ring chain is the nearest hand/finger anatomical chain.
Suspect ring weight is reassigned to the nearest non-ring hand/finger bone so
the vertex remains skinned instead of becoming underweighted.

This is a runtime diagnostic repair. It does NOT modify the canonical GLB.
A permanent source-weight migration should only follow after this proof passes.
"""

from __future__ import annotations

from mathutils import Vector


FINGER_ORDER = ("thumb", "index", "middle", "ring", "pinky")


def _point_segment_distance(point: Vector, a: Vector, b: Vector) -> float:
    ab = b - a
    denom = ab.length_squared
    if denom <= 1e-12:
        return (point - a).length
    t = max(0.0, min(1.0, (point - a).dot(ab) / denom))
    closest = a + ab * t
    return (point - closest).length


def _bone_segment(armature, bone_name: str):
    bone = armature.data.bones[bone_name]
    return bone.head_local.copy(), bone.tail_local.copy()


def _chain_segments(armature, names):
    return [_bone_segment(armature, name) for name in names]


def _distance_to_segments(point, segments):
    return min(_point_segment_distance(point, a, b) for a, b in segments)


def _candidate_targets(armature, mapping, side: str):
    hand = mapping["hands"][side]["hand"]
    targets = {
        "hand": {
            "group": hand,
            "segments": [_bone_segment(armature, hand)],
        }
    }
    for finger in FINGER_ORDER:
        chain = mapping["hands"][side][finger]
        targets[finger] = {
            "group": chain[0],
            "segments": _chain_segments(armature, chain),
        }
    return targets


def sanitize_ring_weights_v0_2(
    armature,
    mapping,
    nearest_margin: float = 1.10,
    absolute_keep_radius: float = 0.045,
):
    report = {
        "policy": "ring must be nearest hand/finger chain; otherwise reassign removed ring weight",
        "nearest_margin": nearest_margin,
        "absolute_keep_radius": absolute_keep_radius,
        "sides": {},
        "removed_total": 0,
        "reassigned_total": 0,
    }

    scene_objects = list(armature.users_scene[0].objects) if armature.users_scene else []

    for side in ("left", "right"):
        ring_chain = mapping["hands"][side]["ring"]
        ring_segments = _chain_segments(armature, ring_chain)
        targets = _candidate_targets(armature, mapping, side)
        competitors = {
            name: data
            for name, data in targets.items()
            if name != "ring"
        }

        side_report = {
            "ring_chain": ring_chain,
            "objects": {},
            "removed_influences": 0,
            "reassigned_vertices": 0,
            "kept_ring_vertices": 0,
        }

        for obj in scene_objects:
            if obj.type != "MESH":
                continue
            if not any(mod.type == "ARMATURE" and mod.object == armature for mod in obj.modifiers):
                continue

            group_by_name = {g.name: g for g in obj.vertex_groups}
            ring_groups = [group_by_name[name] for name in ring_chain if name in group_by_name]
            if not ring_groups:
                continue
            ring_indices = {g.index for g in ring_groups}

            to_armature = armature.matrix_world.inverted() @ obj.matrix_world
            removed_influences = 0
            reassigned_vertices = 0
            kept_vertices = 0
            target_counts = {}

            for vertex in obj.data.vertices:
                ring_assignments = [
                    assignment for assignment in vertex.groups
                    if assignment.group in ring_indices and assignment.weight > 0.0
                ]
                if not ring_assignments:
                    continue

                point = to_armature @ vertex.co
                ring_distance = _distance_to_segments(point, ring_segments)

                nearest_name = None
                nearest_distance = None
                nearest_group_name = None
                for name, target in competitors.items():
                    distance = _distance_to_segments(point, target["segments"])
                    if nearest_distance is None or distance < nearest_distance:
                        nearest_name = name
                        nearest_distance = distance
                        nearest_group_name = target["group"]

                keep_ring = (
                    ring_distance <= absolute_keep_radius
                    and ring_distance <= nearest_distance * nearest_margin
                )
                if keep_ring:
                    kept_vertices += 1
                    continue

                removed_weight = sum(a.weight for a in ring_assignments)

                for group in ring_groups:
                    try:
                        group.remove([vertex.index])
                    except RuntimeError:
                        pass

                if nearest_group_name not in group_by_name:
                    group_by_name[nearest_group_name] = obj.vertex_groups.new(
                        name=nearest_group_name
                    )
                group_by_name[nearest_group_name].add(
                    [vertex.index],
                    removed_weight,
                    "ADD",
                )

                removed_influences += len(ring_assignments)
                reassigned_vertices += 1
                target_counts[nearest_name] = target_counts.get(nearest_name, 0) + 1

            if removed_influences or kept_vertices:
                obj.data.update()
                side_report["objects"][obj.name] = {
                    "removed_influences": removed_influences,
                    "reassigned_vertices": reassigned_vertices,
                    "kept_ring_vertices": kept_vertices,
                    "reassigned_to": target_counts,
                }
                side_report["removed_influences"] += removed_influences
                side_report["reassigned_vertices"] += reassigned_vertices
                side_report["kept_ring_vertices"] += kept_vertices

        report["sides"][side] = side_report
        report["removed_total"] += side_report["removed_influences"]
        report["reassigned_total"] += side_report["reassigned_vertices"]

    return report
