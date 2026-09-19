import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools" / "blender" / "build_opening_reverence_v1.py"
WRAPPER = ROOT / "tools" / "blender" / "run_opening_reverence_v1.ps1"


class Phase104AuthoredPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_source_glb_is_never_overwritten(self) -> None:
        self.assertIn('if input_path == output_path:', self.builder)
        self.assertIn('raise RuntimeError("Refusing to overwrite the source GLB.")', self.builder)
        self.assertIn('build\\phase10_4\\low_poly_girl_authored_v1.glb', self.wrapper)

    def test_audited_ballet_rig_contract_is_explicit(self) -> None:
        for bone in (
            "Hips", "Spine", "Spine 1", "Chest", "Neck", "Head",
            "Clavicle_L", "Clavicle_R",
            "Upper_Arm_L", "Upper_Arm_R", "Lower_Arm_L", "Lower_Arm_R",
            "Hand_L", "Hand_R", "Middle_L", "Middle_R",
            "Upper_Leg_L", "Upper_Leg_R", "Lower_Leg_L", "Lower_Leg_R",
            "Foot_L", "Foot_R", "Toes_L", "Toes_R",
        ):
            self.assertIn(f'"{bone}"', self.builder)

    def test_action_and_duration_contract(self) -> None:
        self.assertIn('ACTION_NAME = "Opening_Reverence_v1"', self.builder)
        self.assertIn("FPS = 30", self.builder)
        self.assertIn("END_FRAME = 68", self.builder)
        self.assertIn('"READY_RESOLUTION"', self.builder)

    def test_pipeline_reports_axes_and_existing_actions(self) -> None:
        self.assertIn('"actions_before": actions_before', self.builder)
        self.assertIn('"actions_after": [action_summary(a) for a in bpy.data.actions]', self.builder)
        self.assertIn('"bone_axes": axes', self.builder)
        self.assertIn('"axis_y_length"', self.builder)

    def test_export_requests_action_animation_mode_when_supported(self) -> None:
        self.assertIn('"export_animations": True', self.builder)
        self.assertIn('"export_animation_mode": "ACTIONS"', self.builder)
        self.assertIn("if key in props:", self.builder)

    def test_wrapper_auto_discovers_blender_and_validates_outputs(self) -> None:
        self.assertIn("Get-Command blender.exe", self.wrapper)
        self.assertIn("Blender Foundation", self.wrapper)
        self.assertIn("PHASE 10.4.1 PIPELINE PASS", self.wrapper)
        self.assertIn("opening_reverence_v1_report.json", self.wrapper)


if __name__ == "__main__":
    unittest.main()
