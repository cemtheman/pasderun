import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
CORE = ROOT / "tools" / "blender" / "build_opening_reverence_v1.py"
LAB = ROOT / "tools" / "blender" / "build_ballet_pose_lab_v1.py"
RUNNER = ROOT / "tools" / "blender" / "run_final_reverence_attempt2.ps1"


class FinalReverenceAttempt2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.core = CORE.read_text(encoding="utf-8")
        cls.lab = LAB.read_text(encoding="utf-8")
        cls.runner = RUNNER.read_text(encoding="utf-8")

    def test_this_is_explicitly_final_attempt_two_of_two(self) -> None:
        self.assertIn('DEFAULT_ATTEMPT = "1/2"', self.lab)
        self.assertIn('parser.add_argument("--attempt", default=DEFAULT_ATTEMPT)', self.lab)
        self.assertIn('--attempt "2/2"', self.runner)
        self.assertIn("FINAL REVERENCE — ATTEMPT 2/2", self.runner)

    def test_pose_lab_disables_imported_action(self) -> None:
        self.assertIn("armature.animation_data_clear()", self.lab)
        self.assertIn("making every arm row look identical", self.lab)

    def test_reverence_is_slow_enough_to_read(self) -> None:
        self.assertIn("END_FRAME = 120", self.core)
        for frame in (14, 34, 56, 72, 94, 108, 120):
            self.assertIn(f'"frame": {frame}', self.core)

    def test_acknowledgement_has_real_descent(self) -> None:
        self.assertIn('"plie": 0.86', self.core)
        self.assertIn("total_leg * 0.145 * plie", self.core)
        self.assertIn('"torso_deg": 11.0', self.core)
        self.assertIn('"head_deg": 6.0', self.core)

    def test_roll_stable_arm_authoring_is_final_model(self) -> None:
        self.assertIn("def set_roll_stable_bone_frame(", self.core)
        self.assertIn("def apply_arm_landmark_pose(", self.core)
        self.assertNotIn('pb.constraints.new("DAMPED_TRACK")', self.core)

    def test_leg_ik_turnout_is_preserved(self) -> None:
        self.assertIn("Phase1045_LegIK_", self.core)
        self.assertIn("turnout @ foot_world_rotations[suffix]", self.core)

    def test_final_run_produces_both_evidence_and_animation(self) -> None:
        self.assertIn("attempt2_final_pose_contact.png", self.runner)
        self.assertIn("final_reverence_attempt2_preview.mp4", self.runner)
        self.assertIn("low_poly_girl_final_reverence_attempt2.glb", self.runner)

    def test_shared_core_phase_contract_remains_compatible(self) -> None:
        self.assertIn('PHASE = "10.4.5"', self.core)
        self.assertIn("PHASE10_4_5=PASS", self.core)
        self.assertIn('$data.phase -ne "10.4.5"', self.runner)

    def test_no_godot_runtime_scope(self) -> None:
        self.assertNotIn("humanoid_motion_controller.gd", self.runner)
        self.assertNotIn("build/web", self.runner)


if __name__ == "__main__":
    unittest.main()
