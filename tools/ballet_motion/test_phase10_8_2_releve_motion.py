from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
TOOLS=REPO/"tools"/"ballet_motion"
if str(TOOLS) not in sys.path:
    sys.path.insert(0,str(TOOLS))

import lower_body_releve_motion as motion  # noqa: E402


class Phase1082ReleveMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract=json.loads(
            (REPO/"assets"/"ballet_motion"/"lower_body_releve_motion_contract_v1.json")
            .read_text(encoding="utf-8")
        )
        cls.intents=json.loads(
            (REPO/"assets"/"ballet_motion"/"foundation_pose_intents_v1.json")
            .read_text(encoding="utf-8")
        )
        cls.constraints=json.loads(
            (REPO/"assets"/"ballet_motion"/"anatomical_constraints_v1.json")
            .read_text(encoding="utf-8")
        )

    def test_contract_and_frame_range(self) -> None:
        motion.validate_contract(self.contract)
        self.assertEqual(motion.frame_end(self.contract),61)
        self.assertEqual(motion.normalized_time(1,self.contract),0.0)
        self.assertEqual(motion.normalized_time(61,self.contract),1.0)

    def test_minimum_jerk_is_bounded_monotone(self) -> None:
        previous=0.0
        for i in range(1001):
            value=motion.minimum_jerk(i/1000.0)
            self.assertGreaterEqual(value,0.0)
            self.assertLessEqual(value,1.0)
            self.assertGreaterEqual(value+1e-12,previous)
            previous=value

    def test_semantic_proxy_stays_preferred(self) -> None:
        for i in range(101):
            evidence=motion.semantic_dof_proxy(
                i/100.0,self.contract,self.intents,self.constraints
            )
            self.assertEqual(evidence["status"],"PASS")

    def test_ankle_and_toe_progress_toward_releve(self) -> None:
        start=motion.semantic_dof_proxy(
            0.0,self.contract,self.intents,self.constraints
        )
        mid=motion.semantic_dof_proxy(
            0.5,self.contract,self.intents,self.constraints
        )
        end=motion.semantic_dof_proxy(
            1.0,self.contract,self.intents,self.constraints
        )
        self.assertEqual(start["joints"]["foot"]["dofs"]["plantar_dorsiflexion"]["value"],0.0)
        self.assertGreater(mid["joints"]["foot"]["dofs"]["plantar_dorsiflexion"]["value"],0.0)
        self.assertEqual(end["joints"]["foot"]["dofs"]["plantar_dorsiflexion"]["value"],35.0)
        self.assertEqual(start["joints"]["toes"]["dofs"]["toe_flexion_extension"]["value"],0.0)
        self.assertGreater(mid["joints"]["toes"]["dofs"]["toe_flexion_extension"]["value"],0.0)
        self.assertEqual(end["joints"]["toes"]["dofs"]["toe_flexion_extension"]["value"],50.0)

    def test_contact_regime_transition_is_explicit(self) -> None:
        interpolation=self.contract["interpolation"]
        self.assertEqual(interpolation["start_contact_mode"],"SOLVE_FULL_FOOT_CONTACT")
        self.assertEqual(interpolation["intermediate_contact_mode"],"SOLVE_FOREFOOT_CONTACT")
        self.assertEqual(interpolation["end_contact_mode"],"SOLVE_FOREFOOT_CONTACT")

    def test_intermediate_joint_search_is_forbidden(self) -> None:
        self.assertTrue(
            self.contract["authority"]["intermediate_plantar_toe_search_forbidden"]
        )

    def test_drift_and_noise_gates_remain_strict(self) -> None:
        v=self.contract["validation"]
        self.assertLessEqual(float(v["locked_local_matrix_error_max"]),1e-7)
        self.assertLessEqual(float(v["moving_scale_error_max"]),1e-6)
        self.assertLessEqual(float(v["accepted_endpoint_decomposition_noise_max"]),5e-6)
        self.assertLessEqual(float(v["root_horizontal_translation_max"]),1e-5)

    def test_releve_requires_meaningful_final_heel_lift(self) -> None:
        self.assertGreaterEqual(
            float(self.contract["validation"]["minimum_final_heel_lift_foot_fraction"]),
            0.05,
        )

    def test_trunk_tilt_returns_toward_vertical(self) -> None:
        start=motion.semantic_dof_proxy(
            0.0,self.contract,self.intents,self.constraints
        )
        end=motion.semantic_dof_proxy(
            1.0,self.contract,self.intents,self.constraints
        )
        self.assertEqual(start["trunk_tilt_deg"],3.0)
        self.assertEqual(end["trunk_tilt_deg"],0.0)


if __name__=="__main__":
    unittest.main()
