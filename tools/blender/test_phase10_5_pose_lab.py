import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "blender" / "build_ballet_pose_lab_v1.py"
WRAPPER = ROOT / "tools" / "blender" / "run_ballet_pose_lab_v1.ps1"


class Phase105PoseLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_attempt_is_explicitly_one_of_two(self) -> None:
        self.assertIn('DEFAULT_ATTEMPT = "1/2"', self.script)
        self.assertIn(
            'parser.add_argument("--attempt", default=DEFAULT_ATTEMPT)',
            self.script,
        )
        self.assertIn("ATTEMPT 1 OF 2", self.wrapper)

    def test_no_animation_or_glb_export(self) -> None:
        self.assertNotIn("export_glb(", self.script)
        self.assertNotIn("bpy.ops.nla.bake", self.script)
        self.assertIn('"animation_rendered": False', self.script)
        self.assertIn('"glb_exported": False', self.script)

    def test_exactly_five_critical_poses(self) -> None:
        for name in (
            "BRAS_BAS",
            "EN_AVANT_PASSAGE",
            "PLACEMENT_AND_SOFTEN",
            "ACKNOWLEDGEMENT",
            "RISE_AND_OPEN",
        ):
            self.assertIn(f'"{name}"', self.script)

    def test_three_views_are_front_three_quarter_side(self) -> None:
        self.assertIn(
            'VIEW_NAMES = ("FRONT", "THREE_QUARTER", "SIDE")',
            self.script,
        )
        self.assertIn("camera_data.type = \"ORTHO\"", self.script)

    def test_same_scale_is_used_for_every_pose(self) -> None:
        self.assertIn("camera_data.ortho_scale = height * 1.14", self.script)
        self.assertIn("center_world", self.script)

    def test_pose_lab_reuses_current_arm_and_leg_authoring(self) -> None:
        self.assertIn("core.apply_arm_landmark_pose(", self.script)
        self.assertIn("core.setup_leg_controls_and_constraints(", self.script)
        self.assertIn("core.key_leg_controls(", self.script)

    def test_blender_52_reads_written_png_not_render_result_pixels(self) -> None:
        self.assertIn(
            'bpy.data.images.load(str(cell_path), check_existing=False)',
            self.script,
        )
        self.assertIn('if not cell_path.exists():', self.script)
        self.assertIn('bpy.data.images.remove(image)', self.script)
        self.assertNotIn(
            'bpy.data.images.get("Render Result")',
            self.script,
        )

    def test_contact_sheet_is_five_by_three(self) -> None:
        self.assertIn("rows * CELL, cols * CELL", self.script)
        self.assertIn("Expected exactly 15 pose views.", self.wrapper)

    def test_output_contract_is_versioned(self) -> None:
        self.assertIn("pose_lab_attempt1_contact.png", self.wrapper)
        self.assertIn("pose_lab_attempt1_report.json", self.wrapper)

    def test_runtime_scope_is_blender_only(self) -> None:
        self.assertNotIn("humanoid_motion_controller.gd", self.script)
        self.assertNotIn("build/web", self.wrapper)


if __name__ == "__main__":
    unittest.main()
