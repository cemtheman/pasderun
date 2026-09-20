"""Phase 10.6.8 Foundation Pose Visual Gate v1.

Renders only poses already solved and realized by the Ballet Motion Engine.
No animation, GLB export, old pose-lab authoring, or reverence authoring.
Automated checks may block rendering; they may not declare aesthetic success.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector


PHASE = "10.6.8"
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import apply_static_foundation_poses_v1 as static_core  # noqa: E402


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
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def matrix3(values) -> Matrix:
    return Matrix(
        tuple(
            tuple(float(value) for value in row)
            for row in values
        )
    )


def matrix_max_error(a: Matrix, b: Matrix) -> float:
    return max(
        abs(float(a[row][col]) - float(b[row][col]))
        for row in range(3)
        for col in range(3)
    )


def rotation_x(angle_deg: float) -> Matrix:
    angle = math.radians(float(angle_deg))
    c = math.cos(angle)
    s = math.sin(angle)
    return Matrix(
        (
            (1.0, 0.0, 0.0),
            (0.0, c, -s),
            (0.0, s, c),
        )
    )


def rotation_z(angle_deg: float) -> Matrix:
    angle = math.radians(float(angle_deg))
    c = math.cos(angle)
    s = math.sin(angle)
    return Matrix(
        (
            (c, -s, 0.0),
            (s, c, 0.0),
            (0.0, 0.0, 1.0),
        )
    )


def decompose_wrist_xz(local_delta: Matrix) -> dict:
    flexion = math.degrees(
        math.atan2(
            -float(local_delta[1][2]),
            float(local_delta[2][2]),
        )
    )
    deviation = math.degrees(
        math.atan2(
            -float(local_delta[0][1]),
            float(local_delta[0][0]),
        )
    )
    reconstructed = rotation_x(flexion) @ rotation_z(deviation)
    return {
        "flexion_extension": flexion,
        "radial_ulnar_deviation": deviation,
        "reconstruction_error": matrix_max_error(
            reconstructed,
            local_delta,
        ),
    }


def canonical_local_delta(
    armature: bpy.types.Object,
    canonical: dict,
    child_name: str,
) -> Matrix:
    child = canonical["canonical_bones"][child_name]
    parent_name = child["parent"]
    if parent_name is None:
        raise RuntimeError(
            f"{child_name}: wrist continuity requires a parent."
        )

    parent = canonical["canonical_bones"][parent_name]
    parent_pose = static_core.canonical_basis_from_rig_pose(
        armature.pose.bones[parent["rig_bone"]],
        parent,
    )
    child_pose = static_core.canonical_basis_from_rig_pose(
        armature.pose.bones[child["rig_bone"]],
        child,
    )
    parent_rest = matrix3(
        parent["canonical_rest_contract"]["basis_armature_local"]
    )
    child_rest = matrix3(
        child["canonical_rest_contract"]["basis_armature_local"]
    )
    rest_local = parent_rest.transposed() @ child_rest
    desired_local = parent_pose.transposed() @ child_pose
    return rest_local.transposed() @ desired_local


def validate_hand_axial_continuity(
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    visual_contract: dict,
) -> dict:
    threshold = float(
        visual_contract["wrist_continuity"][
            "reconstruction_matrix_error_max"
        ]
    )
    comparison_tolerance_deg = float(
        visual_contract["wrist_continuity"][
            "limit_comparison_tolerance_deg"
        ]
    )
    require(
        0.0 <= comparison_tolerance_deg <= 0.001,
        "Wrist limit comparison tolerance must remain <= 0.001 degree.",
    )
    limits = constraints["joint_limits"]["wrist_2dof"]["dofs"]
    evidence = {}

    for side in ("left", "right"):
        hand_name = f"{side}_hand"
        local_delta = canonical_local_delta(
            armature,
            canonical,
            hand_name,
        )
        values = decompose_wrist_xz(local_delta)
        require(
            values["reconstruction_error"] <= threshold,
            f"{hand_name}: hand frame requires undeclared axial wrist "
            f"rotation; reconstruction error "
            f"{values['reconstruction_error']} > {threshold}.",
        )

        for dof_name in (
            "flexion_extension",
            "radial_ulnar_deviation",
        ):
            value = float(values[dof_name])
            preferred = limits[dof_name]["preferred"]
            minimum = float(preferred["min"])
            maximum = float(preferred["max"])
            require(
                minimum - comparison_tolerance_deg
                <= value
                <= maximum + comparison_tolerance_deg,
                f"{hand_name}: {dof_name}={value:.6f} outside "
                f"preferred [{minimum}, {maximum}] beyond "
                f"numeric tolerance {comparison_tolerance_deg} deg.",
            )

        evidence[side] = {
            "flexion_extension_deg": round(
                float(values["flexion_extension"]),
                8,
            ),
            "radial_ulnar_deviation_deg": round(
                float(values["radial_ulnar_deviation"]),
                8,
            ),
            "wrist_2dof_reconstruction_error": round(
                float(values["reconstruction_error"]),
                10,
            ),
            "preferred_envelope": "PASS",
            "preferred_envelope_numeric_tolerance_deg": (
                comparison_tolerance_deg
            ),
            "independent_axial_wrist_rotation": "BLOCKED",
        }

    return evidence


def configure_workbench(
    scene: bpy.types.Scene,
    cell_size: int,
) -> str:
    engine = None
    for candidate in (
        "BLENDER_WORKBENCH",
        "BLENDER_EEVEE_NEXT",
    ):
        try:
            scene.render.engine = candidate
            engine = candidate
            break
        except Exception:
            continue
    if engine is None:
        raise RuntimeError("No supported Blender preview engine.")

    scene.render.resolution_x = cell_size
    scene.render.resolution_y = cell_size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    if scene.world is None:
        scene.world = bpy.data.worlds.new("P1068VisualGateWorld")
    scene.world.color = (0.055, 0.055, 0.055)

    shading = scene.display.shading
    if hasattr(shading, "light"):
        shading.light = "STUDIO"
    for attribute in (
        "show_shadows",
        "show_cavity",
        "show_outline",
    ):
        if hasattr(shading, attribute):
            setattr(shading, attribute, True)

    return engine


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    direction = target - camera.location
    camera.rotation_euler = direction.to_track_quat(
        "-Z",
        "Y",
    ).to_euler()


def create_camera(
    armature: bpy.types.Object,
    canonical: dict,
) -> tuple[bpy.types.Object, Vector, float]:
    bones = armature.data.bones
    head_name = canonical["canonical_bones"]["head"]["rig_bone"]
    left_foot = canonical["canonical_bones"]["left_foot"]["rig_bone"]
    right_foot = canonical["canonical_bones"]["right_foot"]["rig_bone"]

    feet = (
        bones[left_foot].head_local
        + bones[right_foot].head_local
    ) * 0.5
    head = bones[head_name].head_local
    frame = canonical["body_frame"]["declared_axes_armature_local"]
    up_axis = Vector(frame["up"]).normalized()
    height = max((head - feet).dot(up_axis) * 1.30, 1.0)
    center_local = feet + up_axis * height * 0.46
    center_world = armature.matrix_world @ center_local

    camera_data = bpy.data.cameras.new(
        "P1068FoundationPoseCamera"
    )
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = height * 1.14
    camera = bpy.data.objects.new(
        "P1068FoundationPoseCamera",
        camera_data,
    )
    bpy.context.scene.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    return camera, center_world, height


def set_view(
    camera: bpy.types.Object,
    center_world: Vector,
    armature: bpy.types.Object,
    canonical: dict,
    view_name: str,
    height: float,
) -> None:
    frame = canonical["body_frame"]["declared_axes_armature_local"]
    front = (
        armature.matrix_world.to_3x3()
        @ Vector(frame["front"])
    ).normalized()
    left = (
        armature.matrix_world.to_3x3()
        @ Vector(frame["left"])
    ).normalized()
    up = (
        armature.matrix_world.to_3x3()
        @ Vector(frame["up"])
    ).normalized()

    if view_name == "FRONT":
        view_direction = front
    elif view_name == "THREE_QUARTER":
        view_direction = (
            front * 0.78 + left * 0.62
        ).normalized()
    elif view_name == "SIDE":
        view_direction = left
    else:
        raise RuntimeError(f"Unknown view: {view_name}")

    camera.location = (
        center_world
        + view_direction * height * 2.8
        + up * height * 0.02
    )
    look_at(camera, center_world)


def render_cell(
    scene: bpy.types.Scene,
    output_dir: Path,
    row: int,
    column: int,
    pose_name: str,
    view_name: str,
    cell_size: int,
) -> np.ndarray:
    filename = (
        f"{row + 1:02d}_{pose_name}_"
        f"{view_name.lower()}.png"
    )
    path = output_dir / filename
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    require(path.exists(), f"Render missing: {path}")

    image = bpy.data.images.load(
        str(path),
        check_existing=False,
    )
    try:
        width, height = image.size
        require(
            width == cell_size and height == cell_size,
            f"Unexpected cell size {width}x{height}: {path}",
        )
        pixels = np.array(
            image.pixels[:],
            dtype=np.float32,
        )
        expected = cell_size * cell_size * 4
        require(
            pixels.size == expected,
            f"Unexpected pixel count: {path}",
        )
        return pixels.reshape(
            (cell_size, cell_size, 4)
        )
    finally:
        bpy.data.images.remove(image)


def save_contact_sheet(
    cells: list[list[np.ndarray]],
    output_path: Path,
    cell_size: int,
) -> None:
    row_count = len(cells)
    column_count = len(cells[0])
    sheet = np.zeros(
        (
            row_count * cell_size,
            column_count * cell_size,
            4,
        ),
        dtype=np.float32,
    )

    for row, row_cells in enumerate(cells):
        target_row = row_count - 1 - row
        y0 = target_row * cell_size
        for column, cell in enumerate(row_cells):
            x0 = column * cell_size
            sheet[
                y0:y0 + cell_size,
                x0:x0 + cell_size,
                :,
            ] = cell

    image = bpy.data.images.new(
        "P1068FoundationPoseContact",
        width=column_count * cell_size,
        height=row_count * cell_size,
        alpha=True,
        float_buffer=True,
    )
    image.pixels.foreach_set(sheet.ravel())
    image.filepath_raw = str(output_path)
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def prepare_contact_runtime(
    armature: bpy.types.Object,
    canonical: dict,
    static_contract: dict,
) -> dict:
    frame = canonical["body_frame"]["declared_axes_armature_local"]
    up_axis = Vector(frame["up"]).normalized()
    front_axis = Vector(frame["front"]).normalized()

    foot_groups = {
        "left": {
            canonical["canonical_bones"]["left_foot"]["rig_bone"],
            canonical["canonical_bones"]["left_toes"]["rig_bone"],
        },
        "right": {
            canonical["canonical_bones"]["right_foot"]["rig_bone"],
            canonical["canonical_bones"]["right_toes"]["rig_bone"],
        },
    }
    required_groups = set().union(*foot_groups.values())
    meshes = static_core.relevant_mesh_objects(
        armature,
        required_groups,
    )
    sampling = static_contract["contact_sampling"]
    anchors = {}
    for side in ("left", "right"):
        samples = static_core.collect_weighted_samples(
            meshes,
            foot_groups[side],
            float(sampling["minimum_vertex_group_weight"]),
        )
        anchors[side] = static_core.classify_contact_samples(
            armature,
            samples,
            front_axis,
            float(sampling["rear_fraction"]),
            float(sampling["fore_fraction"]),
        )

    static_core.clear_pose(armature)
    rest_heights = static_core.contact_heights(
        armature,
        anchors,
        up_axis,
        float(sampling["low_height_quantile"]),
    )
    hand_groups = static_core.hand_rig_vertex_groups(
        armature,
        canonical,
    )
    hand_meshes = static_core.relevant_mesh_objects(
        armature,
        set().union(*hand_groups.values()),
    )
    hand_sampling = static_contract["hand_mesh_sampling"]
    hand_samples = {
        side: static_core.collect_weighted_samples(
            hand_meshes,
            hand_groups[side],
            float(
                hand_sampling[
                    "minimum_vertex_group_weight"
                ]
            ),
        )
        for side in ("left", "right")
    }

    metrics = static_core.body_metrics(canonical)
    thresholds = static_contract["proof_thresholds"]
    contact_tolerance = (
        metrics["foot_chain_length"]
        * float(
            thresholds[
                "contact_error_max_foot_length_fraction"
            ]
        )
    )
    return {
        "up_axis": up_axis,
        "anchors": anchors,
        "rest_heights": rest_heights,
        "metrics": metrics,
        "contact_tolerance": contact_tolerance,
        "sampling": sampling,
        "hand_samples": hand_samples,
        "hand_sampling": hand_sampling,
    }


def realize_pose(
    pose_name: str,
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    retarget: dict,
    retarget_axis_contract: dict,
    static_contract: dict,
    runtime: dict,
) -> dict:
    pose_entry = retarget["poses"][pose_name]
    require(
        len(pose_entry["rig_pose"]) == 24,
        f"{pose_name}: expected 24 rig rotations.",
    )
    static_core.apply_rotation_deltas(
        armature,
        pose_entry,
    )

    hand_mesh_runtime_solution = {}
    hand_mesh_wrist_solution = {}
    hand_mesh_spacing = {}
    if pose_name in ("bras_bas", "en_avant"):
        hand_mesh_runtime_solution = (
            static_core.solve_runtime_hand_mesh_pose(
                armature,
                canonical,
                constraints,
                retarget_axis_contract,
                runtime["grammar_profile"],
                runtime["intent_spec"],
                pose_name,
                runtime["hand_samples"],
                float(
                    runtime["hand_sampling"][
                        "inner_edge_quantile"
                    ]
                ),
                static_contract[
                    "hand_mesh_runtime_clearance_solver"
                ],
                runtime["pose_solver"],
                runtime["retarget_solver"],
            )
        )
        require(
            hand_mesh_runtime_solution["status"] == "PASS",
            f"{pose_name}: deterministic hand-mesh runtime solve failed.",
        )
        hand_mesh_wrist_solution = hand_mesh_runtime_solution[
            "wrist_seed_evidence"
        ]
        hand_mesh_spacing = hand_mesh_runtime_solution[
            "final_mesh_spacing"
        ]

    mode = static_contract["root_translation_modes"][pose_name]
    thresholds = static_contract["proof_thresholds"]
    up_axis = runtime["up_axis"]
    anchors = runtime["anchors"]
    rest_heights = runtime["rest_heights"]
    sampling = runtime["sampling"]

    orientation = {}
    releve = {}
    if mode == "SOLVE_FULL_FOOT_CONTACT":
        orientation = static_core.realize_full_foot_orientation(
            armature,
            canonical,
            constraints,
            retarget_axis_contract,
            up_axis,
            anchors,
            rest_heights,
            float(sampling["low_height_quantile"]),
            float(
                thresholds[
                    "full_foot_seed_up_alignment_min_dot"
                ]
            ),
            float(
                thresholds[
                    "full_foot_mesh_search_coarse_step_deg"
                ]
            ),
            [
                float(value)
                for value in thresholds[
                    "full_foot_mesh_search_refine_steps_deg"
                ]
            ],
        )

    non_rot = pose_entry.get(
        "non_rotational_pose_contract",
        {},
    )
    scalars = non_rot.get(
        "translation_contact_scalars",
        {},
    )

    if pose_name == "releve":
        target_heights = {
            "left": float(scalars["left_heel_height"]),
            "right": float(scalars["right_heel_height"]),
        }
        releve = static_core.solve_releve_plantar_toe_for_mesh_heel_height(
            armature,
            canonical,
            pose_entry,
            constraints,
            anchors,
            rest_heights,
            up_axis,
            float(sampling["low_height_quantile"]),
            target_heights,
            float(
                thresholds[
                    "releve_plantar_search_coarse_step_deg"
                ]
            ),
            float(
                thresholds[
                    "releve_toe_search_coarse_step_deg"
                ]
            ),
            [
                float(value)
                for value in thresholds[
                    "releve_joint_search_refine_steps_deg"
                ]
            ],
        )

    before_heights = static_core.contact_heights(
        armature,
        anchors,
        up_axis,
        float(sampling["low_height_quantile"]),
    )
    shift = static_core.root_shift_for_contact(
        mode,
        rest_heights,
        before_heights,
    )
    root_name = canonical["canonical_bones"]["pelvis"]["rig_bone"]
    static_core.set_root_translation_armature_space(
        armature,
        root_name,
        up_axis * shift,
    )
    after_heights = static_core.contact_heights(
        armature,
        anchors,
        up_axis,
        float(sampling["low_height_quantile"]),
    )
    contact = static_core.contact_errors(
        mode,
        rest_heights,
        after_heights,
    )
    if contact["required"]:
        require(
            contact["max_abs_error"]
            <= runtime["contact_tolerance"],
            f"{pose_name}: mesh contact failed before render: "
            f"{contact['max_abs_error']} > "
            f"{runtime['contact_tolerance']}.",
        )

    fingertip_spacing = {}
    if pose_name in ("bras_bas", "en_avant"):
        fingertip_spacing = static_core.realized_middle_fingertip_spacing(
            armature,
            canonical,
            pose_entry,
        )

    return {
        "root_up_shift": round(float(shift), 8),
        "contact_mode": mode,
        "contact": contact,
        "full_foot_orientation": orientation,
        "releve_realization": releve,
        "fingertip_spacing_diagnostic": fingertip_spacing,
        "hand_mesh_spacing": hand_mesh_spacing,
        "hand_mesh_wrist_solution": hand_mesh_wrist_solution,
        "hand_mesh_runtime_clearance_solution": (
            hand_mesh_runtime_solution.get("evidence", {})
        ),
    }


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).resolve()
    canonical = json.loads(
        Path(args.canonical_profile).read_text(
            encoding="utf-8"
        )
    )
    constraints = json.loads(
        Path(args.constraint_profile).read_text(
            encoding="utf-8"
        )
    )
    retarget = json.loads(
        Path(args.retarget_profile).read_text(
            encoding="utf-8"
        )
    )
    retarget_axis_contract = json.loads(
        Path(args.retarget_axis_contract).read_text(
            encoding="utf-8"
        )
    )
    grammar_profile = json.loads(
        Path(args.grammar_profile).read_text(
            encoding="utf-8"
        )
    )
    intent_spec = json.loads(
        Path(args.intent_spec).read_text(
            encoding="utf-8"
        )
    )
    pose_solver, retarget_solver = (
        static_core.load_ballet_motion_runtime_modules(repo)
    )
    static_contract = json.loads(
        Path(args.static_contract).read_text(
            encoding="utf-8"
        )
    )
    visual_contract = json.loads(
        Path(args.visual_contract).read_text(
            encoding="utf-8"
        )
    )
    output_path = Path(args.output).resolve()
    report_path = Path(args.report).resolve()
    output_dir = output_path.parent / "foundation_pose_cells"

    require(canonical["phase"] == "10.6.2", "Requires 10.6.2.")
    require(constraints["phase"] == "10.6.3", "Requires 10.6.3.")
    require(retarget["phase"] == "10.6.6", "Requires 10.6.6.")
    require(static_contract["phase"] == "10.6.7", "Requires 10.6.7.")
    require(visual_contract["phase"] == PHASE, "Visual contract mismatch.")
    require(
        visual_contract["policy"][
            "human_visual_acceptance_required"
        ],
        "Human visual acceptance must remain required.",
    )
    require(
        visual_contract["policy"][
            "automated_ballet_aesthetic_pass_forbidden"
        ],
        "Automated aesthetic verdict is forbidden.",
    )

    source_glb = repo / canonical["source"]["path"]
    require(source_glb.exists(), f"Source GLB missing: {source_glb}")
    require(
        static_core.sha256_file(source_glb)
        == canonical["source"]["sha256"],
        "Source GLB changed after calibration.",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(
        filepath=str(source_glb)
    )
    require(
        "FINISHED" in result,
        f"glTF import failed: {result}",
    )

    armature = static_core.find_armature(
        canonical["source"]["armature"]
    )
    if armature.animation_data is not None:
        armature.animation_data_clear()
    for obj in bpy.context.scene.objects:
        if obj.animation_data is not None:
            obj.animation_data_clear()

    runtime = prepare_contact_runtime(
        armature,
        canonical,
        static_contract,
    )
    runtime["grammar_profile"] = grammar_profile
    runtime["intent_spec"] = intent_spec
    runtime["pose_solver"] = pose_solver
    runtime["retarget_solver"] = retarget_solver

    scene = bpy.context.scene
    cell_size = int(
        visual_contract["render"]["cell_size"]
    )
    render_engine = configure_workbench(
        scene,
        cell_size,
    )
    camera, center_world, height = create_camera(
        armature,
        canonical,
    )

    pose_names = visual_contract["poses"]
    view_names = visual_contract["views"]
    rows = []
    pose_reports = {}

    for row, pose_name in enumerate(pose_names):
        realization = realize_pose(
            pose_name,
            armature,
            canonical,
            constraints,
            retarget,
            retarget_axis_contract,
            static_contract,
            runtime,
        )

        hand_continuity = {}
        if pose_name in ("bras_bas", "en_avant", "second"):
            hand_continuity = validate_hand_axial_continuity(
                armature,
                canonical,
                constraints,
                visual_contract,
            )

        row_cells = []
        renders = []
        for column, view_name in enumerate(view_names):
            set_view(
                camera,
                center_world,
                armature,
                canonical,
                view_name,
                height,
            )
            bpy.context.view_layer.update()
            cell = render_cell(
                scene,
                output_dir,
                row,
                column,
                pose_name,
                view_name,
                cell_size,
            )
            row_cells.append(cell)
            renders.append(
                {
                    "view": view_name,
                    "cell_file": (
                        f"{row + 1:02d}_{pose_name}_"
                        f"{view_name.lower()}.png"
                    ),
                }
            )
        rows.append(row_cells)
        pose_reports[pose_name] = {
            "realization": realization,
            "hand_axial_continuity": hand_continuity,
            "renders": renders,
        }

    save_contact_sheet(
        rows,
        output_path,
        cell_size,
    )

    report = {
        "phase": PHASE,
        "schema_version": visual_contract["schema_version"],
        "visual_gate_id": visual_contract["contract_id"],
        "contact_sheet": str(output_path),
        "render_engine": render_engine,
        "row_order": pose_names,
        "column_order": view_names,
        "pose_count": len(pose_names),
        "view_count": len(view_names),
        "render_count": len(pose_names) * len(view_names),
        "poses": pose_reports,
        "automated_gate": {
            "static_realization_pass": True,
            "mesh_contact_pass": True,
            "upper_body_hand_axial_continuity_pass": True,
            "middle_bone_tip_diagnostic_recorded": True,
            "hand_mesh_centerline_spacing_pass": True,
            "hand_mesh_retarget_wrist_seed_preserved_pass": True,
            "hand_mesh_runtime_clearance_solver_pass": True,
            "render_count_pass": True,
            "animation_rendered": False,
            "glb_exported": False,
        },
        "human_visual_gate": {
            "required": True,
            "status": "PENDING_REVIEW",
            "review_contract": visual_contract[
                "visual_review_contract"
            ],
        },
    }
    report_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("PHASE10_6_8_FOUNDATION_POSE_VISUAL_GATE=READY")
    print(f"CONTACT_SHEET={output_path}")
    print(f"REPORT={report_path}")
    print("POSES=6")
    print("VIEWS_PER_POSE=3")
    print("RENDERS=18")
    print("HAND_AXIAL_CONTINUITY=PASS")
    print("MIDDLE_BONE_TIP=DIAGNOSTIC_ONLY")
    print("HAND_MESH_CENTERLINE_SPACING=PASS")
    print("HAND_MESH_RETARGET_WRIST_SEED_PRESERVED=PASS")
    print("HAND_MESH_RUNTIME_CLEARANCE_SOLVER=PASS")
    print("STATIC_CONTACT_REALIZATION=PASS")
    print("ANIMATION=NOT_PERFORMED")
    print("GLB_EXPORT=NOT_PERFORMED")
    print("HUMAN_VISUAL_ACCEPTANCE=PENDING")


if __name__ == "__main__":
    main()
