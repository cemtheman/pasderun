"""Phase 10.5 — Ballet Pose Laboratory, Attempt 1 of 2.

Purpose:
- Do not render animation.
- Do not export GLB.
- Render five critical classical-ballet landmarks from front, 3/4 and side.
- Keep identical orthographic framing so silhouette errors are obvious.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_opening_reverence_v1 as core  # noqa: E402


PHASE = "10.5"
ATTEMPT = "1/2"
POSE_NAMES = (
    "BRAS_BAS",
    "EN_AVANT_PASSAGE",
    "PLACEMENT_AND_SOFTEN",
    "ACKNOWLEDGEMENT",
    "RISE_AND_OPEN",
)
VIEW_NAMES = ("FRONT", "THREE_QUARTER", "SIDE")
CELL = 360


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def pose_by_name(name: str) -> dict:
    for pose in core.POSES:
        if pose["name"] == name:
            return pose
    raise RuntimeError(f"Pose not found: {name}")


def ensure_world(scene: bpy.types.Scene) -> None:
    if scene.world is None:
        scene.world = bpy.data.worlds.new("P105_PoseLabWorld")
    scene.world.color = (0.055, 0.055, 0.055)


def configure_workbench(scene: bpy.types.Scene) -> str:
    engine = core.choose_preview_engine(scene)
    scene.render.resolution_x = CELL
    scene.render.resolution_y = CELL
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.display.shading.light = "STUDIO"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.show_outline = True
    ensure_world(scene)
    return engine


def create_camera(
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    rest: dict[str, Vector],
) -> tuple[bpy.types.Object, Vector, float]:
    feet = (rest["Foot_L"] + rest["Foot_R"]) * 0.5
    head = rest["Head"]
    up = axes["up"]
    height = max((head - feet).dot(up) * 1.30, 1.0)
    center_local = feet + up * height * 0.46
    center_world = core.local_to_world(armature, center_local)

    camera_data = bpy.data.cameras.new("P105_PoseLabCamera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = height * 1.14
    camera = bpy.data.objects.new("P105_PoseLabCamera", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    bpy.context.scene.camera = camera
    return camera, center_world, height


def set_view(
    camera: bpy.types.Object,
    center_world: Vector,
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    view_name: str,
    height: float,
) -> None:
    forward = (armature.matrix_world.to_3x3() @ axes["forward"]).normalized()
    side = (armature.matrix_world.to_3x3() @ axes["side"]).normalized()
    up = (armature.matrix_world.to_3x3() @ axes["up"]).normalized()

    if view_name == "FRONT":
        view_dir = forward
    elif view_name == "THREE_QUARTER":
        view_dir = (forward * 0.78 + side * 0.62).normalized()
    elif view_name == "SIDE":
        view_dir = side
    else:
        raise RuntimeError(view_name)

    camera.location = center_world + view_dir * height * 2.8 + up * height * 0.02
    core.look_at(camera, center_world)


def prepare_leg_controls(
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    rest: dict[str, Vector],
) -> tuple[dict[str, bpy.types.Object], dict[str, object]]:
    scene = bpy.context.scene
    controls, _pole_angles, foot_world_rotations = (
        core.setup_leg_controls_and_constraints(armature, axes, rest)
    )

    for pose in core.POSES:
        frame = int(pose["frame"])
        scene.frame_set(frame)
        core.clear_pose(armature)
        core.apply_body_landmark(armature, axes, rest, pose)
        core.key_leg_controls(
            armature,
            axes,
            rest,
            pose,
            controls,
            foot_world_rotations,
        )
    core.configure_object_interpolation(list(controls.values()))
    return controls, foot_world_rotations


def render_cell(
    scene: bpy.types.Scene,
    output_dir: Path,
    row: int,
    col: int,
    pose_name: str,
    view_name: str,
) -> np.ndarray:
    filename = f"{row + 1:02d}_{pose_name.lower()}_{view_name.lower()}.png"
    scene.render.filepath = str(output_dir / filename)
    bpy.ops.render.render(write_still=True)

    render = bpy.data.images.get("Render Result")
    if render is None:
        raise RuntimeError("Render Result missing.")
    pixels = np.array(render.pixels[:], dtype=np.float32)
    return pixels.reshape((CELL, CELL, 4))


def save_contact_sheet(
    cells: list[list[np.ndarray]],
    output_path: Path,
) -> None:
    rows = len(cells)
    cols = len(cells[0])
    sheet = np.zeros((rows * CELL, cols * CELL, 4), dtype=np.float32)

    # Blender image buffers use bottom-up row order. Keep each rendered cell
    # untouched and reverse only the logical row placement so pose row 1 is
    # visually at the top of the contact sheet.
    for row, row_cells in enumerate(cells):
        target_row = rows - 1 - row
        y0 = target_row * CELL
        for col, cell in enumerate(row_cells):
            x0 = col * CELL
            sheet[y0:y0 + CELL, x0:x0 + CELL, :] = cell

    image = bpy.data.images.new(
        "P105_PoseLabContact",
        width=cols * CELL,
        height=rows * CELL,
        alpha=True,
        float_buffer=True,
    )
    image.pixels.foreach_set(sheet.ravel())
    image.filepath_raw = str(output_path)
    image.file_format = "PNG"
    image.save()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    report_path = Path(args.report).resolve()
    output_dir = output_path.parent

    if not input_path.exists():
        raise FileNotFoundError(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(filepath=str(input_path))
    if "FINISHED" not in result:
        raise RuntimeError(f"glTF import failed: {result}")

    armature = core.find_armature()
    missing = [
        name for name in core.REQUIRED_BONES
        if name not in armature.pose.bones
    ]
    if missing:
        raise RuntimeError(f"Rig contract missing bones: {missing}")

    core.clear_pose(armature)
    axes = core.canonical_axes(armature)
    rest = core.rest_snapshot(armature)
    scene = bpy.context.scene
    scene.frame_start = core.START_FRAME
    scene.frame_end = core.END_FRAME

    engine = configure_workbench(scene)
    camera, center_world, height = create_camera(armature, axes, rest)
    controls, _foot_world_rotations = prepare_leg_controls(
        armature,
        axes,
        rest,
    )

    rows: list[list[np.ndarray]] = []
    rendered = []

    for row, pose_name in enumerate(POSE_NAMES):
        pose = pose_by_name(pose_name)
        scene.frame_set(int(pose["frame"]))
        core.clear_pose(armature)
        core.apply_body_landmark(armature, axes, rest, pose)
        core.apply_arm_landmark_pose(armature, axes, rest, pose)
        bpy.context.view_layer.update()

        row_cells = []
        for col, view_name in enumerate(VIEW_NAMES):
            set_view(
                camera,
                center_world,
                armature,
                axes,
                view_name,
                height,
            )
            bpy.context.view_layer.update()
            cell = render_cell(
                scene,
                output_dir,
                row,
                col,
                pose_name,
                view_name,
            )
            row_cells.append(cell)
            rendered.append(
                {
                    "row": row + 1,
                    "column": col + 1,
                    "pose": pose_name,
                    "view": view_name,
                }
            )
        rows.append(row_cells)

    save_contact_sheet(rows, output_path)

    report = {
        "phase": PHASE,
        "attempt": ATTEMPT,
        "purpose": "static ballet pose validation before animation",
        "source_glb": str(input_path),
        "contact_sheet": str(output_path),
        "render_engine": engine,
        "cell_size": CELL,
        "row_order": list(POSE_NAMES),
        "column_order": list(VIEW_NAMES),
        "renders": rendered,
        "animation_rendered": False,
        "glb_exported": False,
        "arm_authoring": "roll-stable direct bone frames",
        "leg_authoring": "native IK for static pose evaluation",
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    core.remove_controls(controls)

    print("PHASE10_5_POSE_LAB_ATTEMPT_1=PASS")
    print(f"CONTACT={output_path}")
    print(f"REPORT={report_path}")
    print("ROWS=" + " | ".join(POSE_NAMES))
    print("COLUMNS=" + " | ".join(VIEW_NAMES))


if __name__ == "__main__":
    main()
