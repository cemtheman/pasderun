"""Phase 10.8.1 fifth -> plie lower-body foundation-motion proof.

Accepted Phase 10.6 static realizations remain endpoint authority. Intermediate
frames use shortest-arc quaternion interpolation only on endpoint-different
lower-body bones. Pelvis translation is solved every intermediate frame from
the deformed rear+fore foot mesh contact plane. No releve/toe-pivot behavior,
GLB export, gameplay, music, or choreography is permitted here.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


PHASE = "10.8.1"
HERE = Path(__file__).resolve().parent
REPO_DEFAULT = HERE.parents[1]
BALLET_TOOLS = REPO_DEFAULT / "tools" / "ballet_motion"
for path in (HERE, BALLET_TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import apply_static_foundation_poses_v1 as static_core  # noqa: E402
import render_foundation_pose_visual_gate_v1 as visual_gate  # noqa: E402
import lower_body_foundation_motion as motion  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--canonical-profile", required=True)
    parser.add_argument("--constraint-profile", required=True)
    parser.add_argument("--retarget-profile", required=True)
    parser.add_argument("--retarget-axis-contract", required=True)
    parser.add_argument("--grammar-profile", required=True)
    parser.add_argument("--intent-spec", required=True)
    parser.add_argument("--static-contract", required=True)
    parser.add_argument("--visual-contract", required=True)
    parser.add_argument("--motion-contract", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--preview-dir", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def matrix_max_error(a: Matrix, b: Matrix) -> float:
    return max(
        abs(float(a[row][col]) - float(b[row][col]))
        for row in range(4)
        for col in range(4)
    )


def snapshot_local_pose(armature: bpy.types.Object) -> dict[str, Matrix]:
    return {
        bone.name: bone.matrix_basis.copy()
        for bone in armature.pose.bones
    }


def canonical_rig_map(canonical: dict) -> dict[str, str]:
    return {
        name: entry["rig_bone"]
        for name, entry in canonical["canonical_bones"].items()
        if isinstance(entry, dict) and entry.get("rig_bone")
    }


def semantic_driver_rig_names(
    canonical: dict,
    contract: dict,
) -> dict[str, str]:
    mapping = canonical_rig_map(canonical)
    result = {}
    for canonical_name in contract["validation"][
        "semantic_driver_canonical_bones"
    ]:
        require(
            canonical_name in mapping,
            f"Canonical motion driver missing: {canonical_name}.",
        )
        result[canonical_name] = mapping[canonical_name]
    return result


def is_descendant_of_any(
    armature: bpy.types.Object,
    rig_name: str,
    ancestor_names: set[str],
) -> bool:
    bone = armature.pose.bones.get(rig_name)
    if bone is None:
        return False
    parent = bone.parent
    while parent is not None:
        if parent.name in ancestor_names:
            return True
        parent = parent.parent
    return False

def realize_endpoint(
    pose_name: str,
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    retarget: dict,
    retarget_axis_contract: dict,
    static_contract: dict,
    runtime: dict,
) -> tuple[dict[str, Matrix], dict]:
    realization = visual_gate.realize_pose(
        pose_name,
        armature,
        canonical,
        constraints,
        retarget,
        retarget_axis_contract,
        static_contract,
        runtime,
    )
    return snapshot_local_pose(armature), realization


def endpoint_partition(
    armature: bpy.types.Object,
    start_pose: dict[str, Matrix],
    end_pose: dict[str, Matrix],
    canonical: dict,
    contract: dict,
) -> tuple[set[str], set[str], dict]:
    threshold = float(
        contract["validation"]["endpoint_change_detection_error_min"]
    )
    drivers = semantic_driver_rig_names(canonical, contract)
    driver_rig = set(drivers.values())
    reverse = {
        rig: name
        for name, rig in canonical_rig_map(canonical).items()
    }

    raw_errors = {
        name: matrix_max_error(start_pose[name], end_pose[name])
        for name in start_pose
    }
    moving = {
        name
        for name, error in raw_errors.items()
        if error > threshold
    }

    trunk_root_canonical = contract["validation"][
        "trunk_hierarchy_propagation_root"
    ]
    require(
        trunk_root_canonical in drivers,
        "Trunk hierarchy propagation root is not a semantic driver.",
    )
    trunk_root_rig = drivers[trunk_root_canonical]

    hierarchy_followers = {
        name
        for name in moving - driver_rig
        if is_descendant_of_any(
            armature,
            name,
            {trunk_root_rig},
        )
    }
    unexpected = sorted(
        moving - driver_rig - hierarchy_followers
    )
    require(
        not unexpected,
        "fifth -> plie changed bones outside accepted semantic "
        "drivers or trunk hierarchy propagation: "
        + ", ".join(
            f"{name}({reverse.get(name, 'noncanonical')})"
            for name in unexpected
        ),
    )

    required = {
        drivers[name]
        for name in contract["validation"][
            "required_motion_canonical_bones"
        ]
    }
    missing_required = sorted(required - moving)
    require(
        not missing_required,
        "Required fifth -> plie semantic drivers did not change "
        "between accepted endpoints: "
        + ", ".join(missing_required),
    )

    locked = set(start_pose) - moving
    raw_locked_error = max(
        (raw_errors[name] for name in locked),
        default=0.0,
    )
    require(
        raw_locked_error
        <= float(
            contract["validation"][
                "accepted_endpoint_locked_noise_max"
            ]
        ),
        "Accepted locked-bone endpoint noise exceeds ceiling: "
        f"{raw_locked_error}.",
    )

    for name in locked:
        end_pose[name] = start_pose[name].copy()

    locked_after = max(
        (
            matrix_max_error(start_pose[name], end_pose[name])
            for name in locked
        ),
        default=0.0,
    )
    require(
        locked_after
        <= float(
            contract["validation"]["locked_local_matrix_error_max"]
        ),
        f"Locked endpoint canonicalization failed: {locked_after}.",
    )

    return moving, locked, {
        "moving_rig_bones": sorted(moving),
        "semantic_driver_rig_bones": sorted(
            moving & driver_rig
        ),
        "semantic_driver_canonical_bones": sorted(
            reverse.get(name, "noncanonical")
            for name in moving & driver_rig
        ),
        "hierarchy_follower_rig_bones": sorted(
            hierarchy_followers
        ),
        "hierarchy_follower_canonical_bones": sorted(
            reverse.get(name, "noncanonical")
            for name in hierarchy_followers
        ),
        "trunk_hierarchy_propagation_root": (
            trunk_root_canonical
        ),
        "raw_locked_endpoint_local_matrix_error": (
            raw_locked_error
        ),
        "canonicalized_locked_endpoint_local_matrix_error": (
            locked_after
        ),
        "endpoint_change_detection_error_min": threshold,
    }

def prepare_motion_cache(
    start_pose: dict[str, Matrix],
    end_pose: dict[str, Matrix],
    moving: set[str],
    root_name: str,
    contract: dict,
) -> dict:
    translation_limit = float(
        contract["validation"]["moving_non_root_translation_error_max"]
    )
    scale_limit = float(contract["validation"]["moving_scale_error_max"])
    cache = {}

    for rig_name in sorted(moving):
        start_loc, start_q, start_scale = start_pose[rig_name].decompose()
        end_loc, end_q, end_scale = end_pose[rig_name].decompose()
        start_q.normalize()
        end_q.normalize()
        if start_q.dot(end_q) < 0.0:
            end_q.negate()

        translation_error = (end_loc - start_loc).length
        scale_error = (end_scale - start_scale).length
        if rig_name != root_name:
            require(
                translation_error <= translation_limit,
                f"{rig_name}: non-root local translation changed "
                f"{translation_error} > {translation_limit}.",
            )
        require(
            scale_error <= scale_limit,
            f"{rig_name}: local scale changed {scale_error} > {scale_limit}.",
        )

        cache[rig_name] = {
            "location": start_loc.copy(),
            "start_location": start_loc.copy(),
            "end_location": end_loc.copy(),
            "scale": start_scale.copy(),
            "start_quaternion": start_q.copy(),
            "end_quaternion": end_q.copy(),
            "endpoint_angle_deg": math.degrees(
                start_q.rotation_difference(end_q).angle
            ),
            "translation_error": float(translation_error),
            "scale_error": float(scale_error),
        }

    return cache


def root_armature_translation(
    armature: bpy.types.Object,
    root_name: str,
) -> Vector:
    pose_bone = armature.pose.bones[root_name]
    rest_basis = (
        armature.data.bones[root_name].matrix_local.to_3x3().normalized()
    )
    return rest_basis @ Vector(pose_bone.matrix_basis.translation)


def contact_state(
    armature: bpy.types.Object,
    runtime: dict,
    static_contract: dict,
) -> dict:
    mode = "SOLVE_FULL_FOOT_CONTACT"
    heights = static_core.contact_heights(
        armature,
        runtime["anchors"],
        runtime["up_axis"],
        float(runtime["sampling"]["low_height_quantile"]),
    )
    proof = static_core.contact_errors(
        mode,
        runtime["rest_heights"],
        heights,
    )
    return {
        "heights": heights,
        "proof": proof,
    }


def solve_intermediate_full_foot_contact(
    armature: bpy.types.Object,
    canonical: dict,
    runtime: dict,
    static_contract: dict,
    contract: dict,
) -> dict:
    mode = "SOLVE_FULL_FOOT_CONTACT"
    before = static_core.contact_heights(
        armature,
        runtime["anchors"],
        runtime["up_axis"],
        float(runtime["sampling"]["low_height_quantile"]),
    )
    shift = static_core.root_shift_for_contact(
        mode,
        runtime["rest_heights"],
        before,
    )
    root_name = canonical["canonical_bones"]["pelvis"]["rig_bone"]
    static_core.set_root_translation_armature_space(
        armature,
        root_name,
        runtime["up_axis"] * float(shift),
    )
    after = contact_state(armature, runtime, static_contract)
    require(
        after["proof"]["max_abs_error"] <= runtime["contact_tolerance"],
        "Intermediate full-foot mesh contact failed: "
        f"{after['proof']['max_abs_error']} > "
        f"{runtime['contact_tolerance']}; errors={after['proof']['errors']}.",
    )

    root_translation = root_armature_translation(armature, root_name)
    up_axis = runtime["up_axis"]
    up_component = up_axis * root_translation.dot(up_axis)
    horizontal = root_translation - up_component
    horizontal_error = horizontal.length
    require(
        horizontal_error
        <= float(contract["validation"]["root_horizontal_translation_max"]),
        f"Pelvis horizontal drift {horizontal_error} exceeds contract.",
    )

    return {
        "root_up_shift": float(root_translation.dot(up_axis)),
        "root_horizontal_translation": float(horizontal_error),
        "contact": after["proof"],
    }


def set_frame_pose(
    armature: bpy.types.Object,
    start_pose: dict[str, Matrix],
    end_pose: dict[str, Matrix],
    moving: set[str],
    motion_cache: dict,
    canonical: dict,
    runtime: dict,
    static_contract: dict,
    frame: int,
    contract: dict,
) -> dict:
    frame_start = int(contract["transition"]["frame_start"])
    frame_end = motion.frame_end(contract)
    root_name = canonical["canonical_bones"]["pelvis"]["rig_bone"]

    if frame == frame_start:
        target = start_pose
        for name, matrix in target.items():
            armature.pose.bones[name].matrix_basis = matrix.copy()
        bpy.context.view_layer.update()
        state = contact_state(armature, runtime, static_contract)
        root_translation = root_armature_translation(armature, root_name)
        return {
            "frame": frame,
            "progress": 0.0,
            "endpoint_exact": True,
            "root_up_shift": float(
                root_translation.dot(runtime["up_axis"])
            ),
            "root_horizontal_translation": float(
                (
                    root_translation
                    - runtime["up_axis"]
                    * root_translation.dot(runtime["up_axis"])
                ).length
            ),
            "contact": state["proof"],
        }

    if frame == frame_end:
        target = end_pose
        for name, matrix in target.items():
            armature.pose.bones[name].matrix_basis = matrix.copy()
        bpy.context.view_layer.update()
        state = contact_state(armature, runtime, static_contract)
        root_translation = root_armature_translation(armature, root_name)
        return {
            "frame": frame,
            "progress": 1.0,
            "endpoint_exact": True,
            "root_up_shift": float(
                root_translation.dot(runtime["up_axis"])
            ),
            "root_horizontal_translation": float(
                (
                    root_translation
                    - runtime["up_axis"]
                    * root_translation.dot(runtime["up_axis"])
                ).length
            ),
            "contact": state["proof"],
        }

    p = motion.progress(frame, contract)
    for name, matrix in start_pose.items():
        if name not in moving:
            armature.pose.bones[name].matrix_basis = matrix.copy()

    for rig_name in moving:
        item = motion_cache[rig_name]
        bone = armature.pose.bones[rig_name]
        bone.rotation_mode = "QUATERNION"
        q = item["start_quaternion"].slerp(
            item["end_quaternion"],
            p,
        )
        q.normalize()
        bone.rotation_quaternion = q
        bone.scale = item["scale"].copy()
        if rig_name == root_name:
            # Phase 10.6 root contact solve returns an absolute armature-space
            # translation from rest, not an increment from the prior pose.
            # Clear matrix-basis translation before measuring the deformed
            # contact plane so the solver's result can be applied absolutely.
            bone.location = Vector((0.0, 0.0, 0.0))
        else:
            bone.location = item["start_location"].copy()

    bpy.context.view_layer.update()
    contact = solve_intermediate_full_foot_contact(
        armature,
        canonical,
        runtime,
        static_contract,
        contract,
    )
    return {
        "frame": frame,
        "progress": float(p),
        "endpoint_exact": False,
        **contact,
    }


def key_motion(
    armature: bpy.types.Object,
    canonical: dict,
    runtime: dict,
    static_contract: dict,
    start_pose: dict[str, Matrix],
    end_pose: dict[str, Matrix],
    moving: set[str],
    motion_cache: dict,
    contract: dict,
) -> tuple[int, int, dict]:
    frame_start = int(contract["transition"]["frame_start"])
    frame_end = motion.frame_end(contract)

    if armature.animation_data is not None:
        armature.animation_data_clear()

    frame_evidence = []
    root_name = canonical["canonical_bones"]["pelvis"]["rig_bone"]
    previous_shift = None
    epsilon = float(
        contract["validation"]["root_descent_monotonic_epsilon"]
    )

    for frame in range(frame_start, frame_end + 1):
        evidence = set_frame_pose(
            armature,
            start_pose,
            end_pose,
            moving,
            motion_cache,
            canonical,
            runtime,
            static_contract,
            frame,
            contract,
        )
        require(
            evidence["contact"]["max_abs_error"]
            <= runtime["contact_tolerance"],
            f"Frame {frame}: full-foot contact gate failed.",
        )
        if previous_shift is not None:
            require(
                evidence["root_up_shift"]
                <= previous_shift + epsilon,
                f"Frame {frame}: pelvis descent reversed; "
                f"previous={previous_shift}, current="
                f"{evidence['root_up_shift']}, epsilon={epsilon}.",
            )
        previous_shift = evidence["root_up_shift"]
        frame_evidence.append(evidence)

        for rig_name in moving:
            bone = armature.pose.bones[rig_name]
            bone.keyframe_insert(data_path="location", frame=frame)
            if bone.rotation_mode != "QUATERNION":
                bone.rotation_mode = "QUATERNION"
            bone.keyframe_insert(
                data_path="rotation_quaternion",
                frame=frame,
            )
            bone.keyframe_insert(data_path="scale", frame=frame)

    scene = bpy.context.scene
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.render.fps = int(contract["transition"]["fps"])
    scene.frame_set(frame_start)

    return frame_start, frame_end, {
        "method": "LOWER_BODY_SHORTEST_ARC_PLUS_PER_FRAME_FULL_FOOT_CONTACT",
        "sample_count": len(frame_evidence),
        "frames": frame_evidence,
        "root_descent_monotone": True,
        "full_foot_contact_every_frame": True,
    }


def endpoint_error(
    armature: bpy.types.Object,
    target: dict[str, Matrix],
    names: set[str],
) -> float:
    return max(
        (
            matrix_max_error(
                armature.pose.bones[name].matrix_basis,
                target[name],
            )
            for name in names
        ),
        default=0.0,
    )


def validate_motion(
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    intent_spec: dict,
    runtime: dict,
    contract: dict,
    start_pose: dict[str, Matrix],
    end_pose: dict[str, Matrix],
    moving: set[str],
    locked: set[str],
    frame_start: int,
    frame_end: int,
) -> dict:
    locked_limit = float(
        contract["validation"]["locked_local_matrix_error_max"]
    )
    endpoint_limit = float(
        contract["validation"]["endpoint_local_matrix_error_max"]
    )
    quat_limit = float(
        contract["validation"]["minimum_consecutive_quaternion_dot"]
    )
    epsilon = float(
        contract["validation"]["root_descent_monotonic_epsilon"]
    )
    horizontal_limit = float(
        contract["validation"]["root_horizontal_translation_max"]
    )

    root_name = canonical["canonical_bones"]["pelvis"]["rig_bone"]
    previous_shift = None
    previous_q = {}
    minimum_q_dot = 1.0
    maximum_q_step_deg = 0.0
    max_locked_error = 0.0
    max_contact_error = 0.0
    max_horizontal_root = 0.0
    root_shifts = []
    frames = []

    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()

        locked_error = max(
            (
                matrix_max_error(
                    armature.pose.bones[name].matrix_basis,
                    start_pose[name],
                )
                for name in locked
            ),
            default=0.0,
        )
        max_locked_error = max(max_locked_error, locked_error)
        require(
            locked_error <= locked_limit,
            f"Frame {frame}: locked local drift "
            f"{locked_error} > {locked_limit}.",
        )

        contact = contact_state(
            armature,
            runtime,
            {},
        )["proof"]
        max_contact_error = max(
            max_contact_error,
            float(contact["max_abs_error"]),
        )
        require(
            contact["max_abs_error"] <= runtime["contact_tolerance"],
            f"Frame {frame}: full-foot contact error "
            f"{contact['max_abs_error']} > "
            f"{runtime['contact_tolerance']}.",
        )

        root_translation = root_armature_translation(
            armature,
            root_name,
        )
        up = runtime["up_axis"]
        shift = float(root_translation.dot(up))
        horizontal = (
            root_translation - up * root_translation.dot(up)
        ).length
        max_horizontal_root = max(max_horizontal_root, horizontal)
        require(
            horizontal <= horizontal_limit,
            f"Frame {frame}: pelvis horizontal drift "
            f"{horizontal} > {horizontal_limit}.",
        )
        if previous_shift is not None:
            require(
                shift <= previous_shift + epsilon,
                f"Frame {frame}: pelvis descent reversed; "
                f"{shift} > {previous_shift} + {epsilon}.",
            )
        previous_shift = shift
        root_shifts.append(shift)

        semantic = motion.semantic_dof_proxy(
            motion.normalized_time(frame, contract),
            contract,
            intent_spec,
            constraints,
        )
        require(
            semantic["status"] == "PASS",
            f"Frame {frame}: lower-body semantic preferred envelope failed.",
        )

        for rig_name in moving:
            q = armature.pose.bones[
                rig_name
            ].matrix_basis.to_quaternion()
            q.normalize()
            prior = previous_q.get(rig_name)
            if prior is not None:
                dot = float(prior.dot(q))
                if dot < 0.0:
                    q.negate()
                    dot = float(prior.dot(q))
                minimum_q_dot = min(minimum_q_dot, dot)
                require(
                    dot >= quat_limit - 1e-9,
                    f"Frame {frame}: quaternion flip on "
                    f"{rig_name}: {dot}.",
                )
                step = math.degrees(
                    prior.rotation_difference(q).angle
                )
                maximum_q_step_deg = max(
                    maximum_q_step_deg,
                    step,
                )
            previous_q[rig_name] = q.copy()

        frames.append(
            {
                "frame": frame,
                "normalized_t": round(
                    motion.normalized_time(frame, contract),
                    8,
                ),
                "progress": round(
                    motion.progress(frame, contract),
                    8,
                ),
                "root_up_shift": round(shift, 8),
                "root_horizontal_translation": round(
                    float(horizontal),
                    8,
                ),
                "contact_max_abs_error": float(
                    contact["max_abs_error"]
                ),
                "semantic_preferred_envelope_proxy": (
                    semantic["status"]
                ),
                "locked_local_matrix_error": locked_error,
            }
        )

    bpy.context.scene.frame_set(frame_start)
    start_error = endpoint_error(
        armature,
        start_pose,
        moving,
    )
    bpy.context.scene.frame_set(frame_end)
    end_error = endpoint_error(
        armature,
        end_pose,
        moving,
    )
    require(
        start_error <= endpoint_limit,
        f"Start endpoint error {start_error} > {endpoint_limit}.",
    )
    require(
        end_error <= endpoint_limit,
        f"End endpoint error {end_error} > {endpoint_limit}.",
    )
    require(
        root_shifts[-1] < root_shifts[0],
        "Plié endpoint did not descend below fifth.",
    )

    return {
        "start_endpoint_local_matrix_error": start_error,
        "end_endpoint_local_matrix_error": end_error,
        "maximum_locked_local_matrix_error": max_locked_error,
        "maximum_full_foot_contact_error": max_contact_error,
        "contact_tolerance": float(runtime["contact_tolerance"]),
        "maximum_root_horizontal_translation": float(
            max_horizontal_root
        ),
        "root_up_shift_start": float(root_shifts[0]),
        "root_up_shift_end": float(root_shifts[-1]),
        "root_descent": float(root_shifts[0] - root_shifts[-1]),
        "root_descent_monotone": True,
        "minimum_consecutive_quaternion_dot": minimum_q_dot,
        "maximum_consecutive_quaternion_step_deg": (
            maximum_q_step_deg
        ),
        "sample_count": len(frames),
        "sampled_every_frame": True,
        "frames": frames,
    }


def configure_video_output(scene: bpy.types.Scene) -> str:
    image_settings = scene.render.image_settings
    media_property = image_settings.bl_rna.properties.get(
        "media_type"
    )
    if media_property is not None:
        values = {
            item.identifier for item in media_property.enum_items
        }
        if "VIDEO" in values:
            image_settings.media_type = "VIDEO"
            return "MEDIA_TYPE_VIDEO"

    format_property = image_settings.bl_rna.properties.get(
        "file_format"
    )
    if format_property is not None:
        values = {
            item.identifier for item in format_property.enum_items
        }
        if "FFMPEG" in values:
            image_settings.file_format = "FFMPEG"
            return "FILE_FORMAT_FFMPEG"

    raise RuntimeError("Blender exposes no supported video output API.")


def render_previews(
    armature: bpy.types.Object,
    canonical: dict,
    contract: dict,
    preview_dir: Path,
    frame_start: int,
    frame_end: int,
) -> tuple[list[str], dict]:
    preview_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    resolution = int(contract["preview"]["resolution"])
    engine = visual_gate.configure_workbench(
        scene,
        resolution,
    )
    video_api = configure_video_output(scene)

    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.render.fps = int(contract["transition"]["fps"])
    scene.render.ffmpeg.format = contract["preview"]["container"]
    scene.render.ffmpeg.codec = contract["preview"]["codec"]
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"

    scene.frame_set(frame_start)
    camera, center_world, height = visual_gate.create_camera(
        armature,
        canonical,
    )

    paths = []
    for view_name in contract["preview"]["views"]:
        visual_gate.set_view(
            camera,
            center_world,
            armature,
            canonical,
            view_name,
            height,
        )
        path = preview_dir / (
            f"fifth_to_plie_{view_name.lower()}.mp4"
        )
        if path.exists():
            path.unlink()
        scene.render.filepath = str(path)
        result = bpy.ops.render.render(animation=True)
        require(
            "FINISHED" in result,
            f"{view_name}: preview render failed: {result}",
        )
        require(
            path.exists(),
            f"{view_name}: preview missing: {path}",
        )
        paths.append(str(path))

    return paths, {
        "engine": engine,
        "video_output_api": video_api,
        "views": list(contract["preview"]["views"]),
        "resolution": resolution,
    }


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).resolve()
    canonical = load_json(args.canonical_profile)
    constraints = load_json(args.constraint_profile)
    retarget = load_json(args.retarget_profile)
    retarget_axis_contract = load_json(
        args.retarget_axis_contract
    )
    grammar_profile = load_json(args.grammar_profile)
    intent_spec = load_json(args.intent_spec)
    static_contract = load_json(args.static_contract)
    visual_contract = load_json(args.visual_contract)
    contract = load_json(args.motion_contract)
    report_path = Path(args.report).resolve()
    preview_dir = Path(args.preview_dir).resolve()

    motion.validate_contract(contract)
    require(
        canonical["phase"] == "10.6.2",
        "Requires accepted Phase 10.6.2.",
    )
    require(
        constraints["phase"] == "10.6.3",
        "Requires accepted Phase 10.6.3.",
    )
    require(
        retarget["phase"] == "10.6.6",
        "Requires accepted Phase 10.6.6.",
    )
    require(
        static_contract["phase"] == "10.6.7",
        "Requires accepted Phase 10.6.7.",
    )
    require(
        visual_contract["phase"] == "10.6.8",
        "Requires accepted Phase 10.6.8.",
    )
    require(
        retarget["gate"]["orientation_retarget_pass"],
        "Accepted retarget gate is not PASS.",
    )

    source_glb = repo / canonical["source"]["path"]
    require(
        source_glb.exists(),
        f"Source GLB missing: {source_glb}",
    )
    require(
        static_core.sha256_file(source_glb)
        == canonical["source"]["sha256"],
        "Source GLB changed after accepted rig calibration.",
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    imported = bpy.ops.import_scene.gltf(
        filepath=str(source_glb)
    )
    require(
        "FINISHED" in imported,
        f"glTF import failed: {imported}",
    )
    armature = static_core.find_armature(
        canonical["source"]["armature"]
    )

    if armature.animation_data is not None:
        armature.animation_data_clear()
    for obj in bpy.context.scene.objects:
        if obj.animation_data is not None:
            obj.animation_data_clear()

    runtime = visual_gate.prepare_contact_runtime(
        armature,
        canonical,
        static_contract,
    )
    pose_solver, retarget_solver = (
        static_core.load_ballet_motion_runtime_modules(repo)
    )
    runtime["grammar_profile"] = grammar_profile
    runtime["intent_spec"] = intent_spec
    runtime["pose_solver"] = pose_solver
    runtime["retarget_solver"] = retarget_solver

    start_name = contract["transition"]["start_pose"]
    end_name = contract["transition"]["end_pose"]
    start_pose, start_evidence = realize_endpoint(
        start_name,
        armature,
        canonical,
        constraints,
        retarget,
        retarget_axis_contract,
        static_contract,
        runtime,
    )
    end_pose, end_evidence = realize_endpoint(
        end_name,
        armature,
        canonical,
        constraints,
        retarget,
        retarget_axis_contract,
        static_contract,
        runtime,
    )

    moving, locked, partition = endpoint_partition(
        armature,
        start_pose,
        end_pose,
        canonical,
        contract,
    )
    root_name = canonical["canonical_bones"]["pelvis"]["rig_bone"]
    require(
        root_name in moving,
        "Pelvis must be part of fifth -> plie moving set.",
    )
    motion_cache = prepare_motion_cache(
        start_pose,
        end_pose,
        moving,
        root_name,
        contract,
    )

    for name, matrix in start_pose.items():
        armature.pose.bones[name].matrix_basis = matrix.copy()
    bpy.context.view_layer.update()

    frame_start, frame_end, generation = key_motion(
        armature,
        canonical,
        runtime,
        static_contract,
        start_pose,
        end_pose,
        moving,
        motion_cache,
        contract,
    )
    diagnostics = validate_motion(
        armature,
        canonical,
        constraints,
        intent_spec,
        runtime,
        contract,
        start_pose,
        end_pose,
        moving,
        locked,
        frame_start,
        frame_end,
    )
    preview_paths, preview_evidence = render_previews(
        armature,
        canonical,
        contract,
        preview_dir,
        frame_start,
        frame_end,
    )

    report = {
        "phase": PHASE,
        "contract_id": contract["contract_id"],
        "transition": contract["transition"],
        "authority": contract["authority"],
        "endpoint_realization": {
            start_name: start_evidence,
            end_name: end_evidence,
        },
        "endpoint_partition": partition,
        "moving_bones": {
            name: {
                "endpoint_angle_deg": round(
                    float(item["endpoint_angle_deg"]),
                    8,
                ),
                "translation_error": float(
                    item["translation_error"]
                ),
                "scale_error": float(item["scale_error"]),
            }
            for name, item in motion_cache.items()
        },
        "motion_generation": generation,
        "diagnostics": diagnostics,
        "preview": {
            **preview_evidence,
            "files": preview_paths,
        },
        "automated_gate": {
            "accepted_static_endpoints_reused": True,
            "start_endpoint_exact": True,
            "end_endpoint_exact": True,
            "phase10_6_endpoint_motion_authority": True,
            "accepted_trunk_hierarchy_motion": True,
            "quaternion_shortest_arc": True,
            "minimum_jerk_timing": True,
            "full_foot_contact_every_frame": True,
            "pelvis_descent_monotone": True,
            "root_horizontal_drift_blocked": True,
            "nonparticipating_bones_stable": True,
            "semantic_preferred_envelope_proxy": True,
            "quaternion_flip_free": True,
            "releve_scope_absent": True,
            "glb_exported": False,
        },
        "human_visual_gate": {
            "required": bool(
                contract["preview"][
                    "human_visual_acceptance_required"
                ]
            ),
            "status": "PENDING_REVIEW",
            "question": (
                "Does fifth to plie read as coordinated turnout and "
                "descent with full-foot contact, rather than a squat/frog?"
            ),
            "automated_aesthetic_verdict": False,
        },
    }

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    report_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("PHASE10_8_1_LOWER_BODY_MOTION_AUTOMATED_PROOF=PASS")
    print(f"REPORT={report_path}")
    print(f"PREVIEWS={';'.join(preview_paths)}")
    print("HUMAN_VISUAL_REVIEW=PENDING")
    print("GLB_EXPORT=NOT_PERFORMED")


if __name__ == "__main__":
    main()
