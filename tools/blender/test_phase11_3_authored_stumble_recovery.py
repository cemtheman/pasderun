from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER = (ROOT / "tools/blender/build_stumble_recovery_v1.py").read_text(
    encoding="utf-8"
)
RUNNER = (
    ROOT / "tools/blender/run_phase11_3_authored_stumble_recovery.ps1"
).read_text(encoding="utf-8")
CONTRACT = json.loads(
    (
        ROOT
        / "data/choreography/stumble_recovery_v1.retarget_contract.json"
    ).read_text(encoding="utf-8")
)


class Phase113AuthoredStumbleRecoveryTests(unittest.TestCase):
    def test_source_is_the_authored_runner_action(self) -> None:
        self.assertEqual(CONTRACT["source"]["expected_armature"], "Runner_RIG")
        self.assertEqual(CONTRACT["source"]["expected_action"], "Runner_RIGAction")
        self.assertEqual(CONTRACT["source"]["expected_frame_count"], 49)
        self.assertIn("49", RUNNER)
        self.assertIn("outputs\\tokezleme\\_toparlanma.blend", RUNNER)

    def test_source_phase_markers_are_locked(self) -> None:
        self.assertEqual(
            CONTRACT["source"]["labels"],
            [
                "RUN",
                "TOE CATCH",
                "MOMENTUM FORWARD",
                "PEAK STUMBLE",
                "LEFT CATCH STEP",
                "RECOVERY",
                "RIGHT SUPPORT",
                "RUN RESUMES",
                "STABLE RUN",
            ],
        )
        self.assertIn("timeline_markers", BUILDER)
        self.assertIn("Source authored phase markers missing", BUILDER)

    def test_target_is_existing_low_poly_girl_rig(self) -> None:
        self.assertEqual(
            CONTRACT["target"]["glb"],
            "assets/characters/low_poly_girl/low_poly_girl .glb",
        )
        self.assertEqual(CONTRACT["target"]["expected_armature"], "Rig")
        self.assertIn('ACTION_NAME = "stumble_recovery_v1"', BUILDER)

    def test_core_limb_mapping_is_explicit(self) -> None:
        mapping = CONTRACT["retarget"]["source_to_target"]
        expected = {
            "pelvis": ["Hips"],
            "thigh.L": ["Upper_Leg_L"],
            "shin.L": ["Lower_Leg_L"],
            "foot.L": ["Foot_L"],
            "thigh.R": ["Upper_Leg_R"],
            "shin.R": ["Lower_Leg_R"],
            "foot.R": ["Foot_R"],
            "upper_arm.L": ["Upper_Arm_L"],
            "forearm.L": ["Lower_Arm_L"],
            "hand.L": ["Hand_L"],
            "upper_arm.R": ["Upper_Arm_R"],
            "forearm.R": ["Lower_Arm_R"],
            "hand.R": ["Hand_R"],
        }
        for source, target in expected.items():
            self.assertEqual(mapping[source], target)

    def test_spine_motion_is_distributed_without_parallel_authority(self) -> None:
        self.assertEqual(
            CONTRACT["retarget"]["source_to_target"]["spine"],
            ["Spine", "Spine 1", "Chest"],
        )
        self.assertEqual(
            CONTRACT["retarget"]["spine_distribution"],
            {"Spine": 0.34, "Spine 1": 0.67, "Chest": 1.0},
        )
        self.assertNotIn("mannequin", BUILDER.lower())

    def test_forward_root_motion_stays_gameplay_owned(self) -> None:
        policy = CONTRACT["retarget"]["root_motion_policy"]
        self.assertEqual(policy["forward_translation"], "remove")
        self.assertEqual(policy["lateral_translation"], "preserve_scaled")
        self.assertEqual(policy["vertical_translation"], "preserve_scaled")
        self.assertIn("body_root.z = 0.0", BUILDER)
        self.assertIn("forward root translation", BUILDER.lower())

    def test_retarget_uses_landmark_directions_and_declared_target_frame(self) -> None:
        self.assertEqual(
            CONTRACT["retarget"]["rotation_transfer"],
            "pose_landmark_direction_roll_stable",
        )
        self.assertIn("pose_heads", BUILDER)
        self.assertIn("pose_tails", BUILDER)
        self.assertIn("def mapped_source_direction(", BUILDER)
        self.assertIn("def set_roll_stable_direction(", BUILDER)
        self.assertIn("def apply_landmark_retarget_frame(", BUILDER)
        self.assertIn("declared_target_frame(seed)", BUILDER)
        self.assertNotIn("@ source_delta", BUILDER)

    def test_frame1_direction_gate_is_reported(self) -> None:
        self.assertIn("frame1_direction_evidence", BUILDER)
        self.assertIn('"frame1_direction_alignment"', BUILDER)
        self.assertIn(
            '"rotation_transfer": "pose_landmark_direction_roll_stable"',
            BUILDER,
        )

    def test_preview_camera_uses_world_space_and_lit_render(self) -> None:
        self.assertIn(
            'world_basis = armature.matrix_world.to_3x3()',
            BUILDER,
        )
        self.assertIn(
            'return armature.matrix_world @ armature.pose.bones[name].matrix.translation',
            BUILDER,
        )
        self.assertIn(
            '"BLENDER_EEVEE_NEXT"',
            BUILDER,
        )
        self.assertIn(
            'assign_preview_material(preview_material)',
            BUILDER,
        )
        self.assertIn(
            'add_area_light(',
            BUILDER,
        )

    def test_preview_has_non_black_proof_gate(self) -> None:
        self.assertIn(
            'proof_path = preview_path.with_name(',
            BUILDER,
        )
        self.assertIn(
            'configure_image_output(scene)',
            BUILDER,
        )
        self.assertIn(
            'image_settings.media_type = "IMAGE"',
            BUILDER,
        )
        self.assertIn(
            'bpy.ops.render.render(write_still=True)',
            BUILDER,
        )
        self.assertIn(
            'luminance = rendered_image_luminance(proof_path)',
            BUILDER,
        )
        self.assertIn(
            'bpy.data.images.load(',
            BUILDER,
        )
        self.assertIn(
            'Saved proof image contains no pixels',
            BUILDER,
        )
        self.assertIn(
            'Preview proof does not contain a visible character',
            BUILDER,
        )
        self.assertIn(
            'luminance["alpha_coverage"] > 0.002',
            BUILDER,
        )
        self.assertIn(
            'scene.render.film_transparent = True',
            BUILDER,
        )
        self.assertIn(
            'floor.hide_render = True',
            BUILDER,
        )

    def test_preview_is_human_gate_before_runtime_integration(self) -> None:
        self.assertEqual(
            CONTRACT["preview"]["renderer"],
            "BLENDER_EEVEE_NEXT_OR_EEVEE",
        )
        self.assertIn("stumble_recovery_v1_preview.mp4", RUNNER)
        self.assertIn("--python-exit-code 1", RUNNER)
        self.assertIn("Remove-Item -Force", RUNNER)
        self.assertIn("Preview proof image missing", RUNNER)
        self.assertNotIn("humanoid_motion_controller.gd", BUILDER)
        self.assertNotIn("run_recovery_manager.gd", BUILDER)
        self.assertNotIn("build/web", RUNNER.lower())


if __name__ == "__main__":
    unittest.main()
