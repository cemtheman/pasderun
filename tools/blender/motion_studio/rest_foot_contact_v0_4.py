"""Measure candidate rest-pose foot sole patches on the final Rig mesh.

This is a diagnostic. It does not infer center of mass or animate a pose.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


MOTION_TOOLS = Path(__file__).resolve().parents[2] / "motion_studio"
sys.path.insert(0, str(MOTION_TOOLS))
from contact_support import dot, hull, solve_contact_support  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402


def args_from_blender():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def candidate_vertices(armature, calibration, side):
    names = {calibration["canonical_bones"][f"{side}_{part}"]["rig_bone"]
             for part in ("foot", "toes")}
    other = "right" if side == "left" else "left"
    other_names = {calibration["canonical_bones"][f"{other}_{part}"]["rig_bone"]
                   for part in ("foot", "toes")}
    candidates = []
    to_local = armature.matrix_world.inverted()
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or not any(mod.type == "ARMATURE" and mod.object == armature for mod in obj.modifiers):
            continue
        group_by_index = {group.index: group.name for group in obj.vertex_groups}
        transform = to_local @ obj.matrix_world
        for vertex in obj.data.vertices:
            weights = {group_by_index[g.group]: g.weight for g in vertex.groups if g.group in group_by_index}
            side_weight = max((weights.get(name, 0) for name in names), default=0)
            opposite_weight = max((weights.get(name, 0) for name in other_names), default=0)
            if side_weight < 0.1 or side_weight <= opposite_weight:
                continue
            position = transform @ vertex.co
            candidates.append((list(position), f"{obj.name}:vertex:{vertex.index}"))
    require(candidates, f"No weighted mesh vertices for {side} foot/toes")
    return candidates


def select_patch(candidates, frame, height, side):
    up = frame["up"]
    minimum = min(dot(point, up) for point, _ in candidates)
    band = max(0.0075 * height, 1e-5)
    near_sole = [(point, reference) for point, reference in candidates if dot(point, up) <= minimum + band]
    positions = {}
    for point, reference in near_sole:
        key = (dot(point, frame["left"]), dot(point, frame["front"]))
        if key not in positions or dot(point, up) < dot(positions[key][0], up):
            positions[key] = (point, reference)
    outline, _area = hull(list(positions))
    return {
        "id": f"{side}_sole", "side": side,
        "source": {"kind": "measured_mesh", "reference": f"rest pose weighted Foot/Toes mesh vertices; up band={band:.8f}"},
        "points": [{"position_armature_local": positions[key][0], "reference": positions[key][1]}
                   for key in outline],
    }, {"candidate_count": len(candidates), "near_sole_count": len(near_sole),
        "hull_count": len(outline), "lowest_up": minimum, "band": band}


def top_view_svg(spec, result):
    frame = spec["anatomical_frame"]
    polygon = result["support_polygon_left_front"]
    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
    center_x, center_y = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    scale = min(350/max(max(xs)-min(xs), 1e-6), 350/max(max(ys)-min(ys), 1e-6))

    def xy(point):
        return f"{250+(point[0]-center_x)*scale:.2f},{250-(point[1]-center_y)*scale:.2f}"

    layers = []
    for patch, color in zip(spec["patches"], ("#4794c8", "#e7a45e")):
        footprint, _ = hull([(dot(p["position_armature_local"], frame["left"]),
                              dot(p["position_armature_local"], frame["front"])) for p in patch["points"]])
        layers.append(f'<polygon points="{" ".join(xy(p) for p in footprint)}" fill="{color}" fill-opacity="0.45" stroke="{color}" stroke-width="2"/>')
    layers.append(f'<polygon points="{" ".join(xy(p) for p in polygon)}" fill="none" stroke="#ffffff" stroke-width="3"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="500" height="540" viewBox="0 0 500 540">'
            '<rect width="500" height="540" fill="#17202b"/>'
            '<text x="20" y="28" fill="white" font-family="sans-serif" font-size="16">Rest sole support — body left / front</text>'
            + "".join(layers) +
            '<text x="20" y="520" fill="white" font-family="sans-serif" font-size="14">COM unknown; balance not evaluated</text></svg>')


def main():
    args = args_from_blender()
    repo = args.repo.resolve()
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    rig = json.loads((repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(encoding="utf-8"))
    seed = json.loads((repo / rig["calibration_seed"]).read_text(encoding="utf-8"))
    validate_calibration(calibration, rig, seed, repo)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE" and obj.name == rig["armature"]]
    require(len(armatures) == 1, "Expected exactly one final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    frame = calibration["anatomical_frame"]
    head = calibration["canonical_bones"]["head"]["head_local"]
    feet = [calibration["canonical_bones"][f"{side}_foot"]["head_local"] for side in ("left", "right")]
    height = dot(head, frame["up"]) - sum(dot(foot, frame["up"]) for foot in feet)/2
    require(height > 0, "Degenerate measured standing height")
    patches = []
    counts = {}
    for side in ("left", "right"):
        patch, counts[side] = select_patch(candidate_vertices(armature, calibration, side), frame, height, side)
        patches.append(patch)
    spec = {"schema_version": "0.4.0", "pose_id": "final_rig_rest_contact_probe_v0_4",
            "rig_profile_id": calibration["rig_profile_id"],
            "source_glb_sha256": calibration["source"]["sha256"],
            "anatomical_frame": frame, "ground_height_up": 0,
            "max_contact_height_spread": 0.015 * height,
            "patches": patches, "active_patch_ids": [p["id"] for p in patches]}
    result = solve_contact_support(spec, calibration)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "foot_patches.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    report = {"status": "CONTACT_GEOMETRY_PASS_BALANCE_UNKNOWN", "result": result,
              "extraction": counts, "limits": "Rest mesh sole band is a candidate footprint; no measured COM, physics or animation"}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "support_top.svg").write_text(top_view_svg(spec, result), encoding="utf-8")
    print("MOTION_STUDIO_V0_4_CONTACT=PASS_BALANCE_UNKNOWN")
    print(f"REPORT={output / 'report.json'}")
    print(f"TOP_VIEW={output / 'support_top.svg'}")


if __name__ == "__main__":
    main()
