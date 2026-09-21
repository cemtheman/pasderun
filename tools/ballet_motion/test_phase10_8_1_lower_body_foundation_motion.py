from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools" / "ballet_motion"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import lower_body_foundation_motion as motion  # noqa: E402


class Phase1081LowerBodyFoundationMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(
            (
                REPO
                / "assets"
                / "ballet_motion"
                / "lower_body_foundation_motion_contract_v1.json"
            ).read_text(encoding="utf-8")
        )
        cls.intents = json.loads(
            (
                REPO
                / "assets"
                / "ballet_motion"
                / "foundation_pose_intents_v1.json"
            ).read_text(encoding="utf-8")
        )
        cls.constraints = json.loads(
            (
                REPO
                / "assets"
                / "ballet_motion"
                / "anatomical_constraints_v1.json"
            ).read_text(encoding="utf-8")
        )

    def test_contract_and_frame_range(self) -> None:
        motion.validate_contract(self.contract)
        self.assertEqual(motion.frame_end(self.contract), 61)
        self.assertEqual(motion.normalized_time(1, self.contract), 0.0)
        self.assertEqual(motion.normalized_time(61, self.contract), 1.0)

    def test_minimum_jerk_is_exact_bounded_and_monotone(self) -> None:
        previous = 0.0
        for index in range(1001):
            p = motion.minimum_jerk(index / 1000.0)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)
            self.assertGreaterEqual(p + 1e-12, previous)
            previous = p
        self.assertEqual(motion.minimum_jerk(0.0), 0.0)
        self.assertEqual(motion.minimum_jerk(1.0), 1.0)

    def test_single_progress_has_no_role_stagger(self) -> None:
        values = [
            motion.progress(frame, self.contract)
            for frame in range(1, 62)
        ]
        self.assertEqual(values[0], 0.0)
        self.assertEqual(values[-1], 1.0)
        self.assertEqual(values, sorted(values))

    def test_bounded_scalar_interpolation_has_no_overshoot(self) -> None:
        for start, end in ((5.0, 32.0), (45.0, 45.0), (0.0, 18.0)):
            lo = min(start, end)
            hi = max(start, end)
            for index in range(101):
                value = motion.interpolate_bounded_scalar(
                    start,
                    end,
                    index / 100.0,
                )
                self.assertGreaterEqual(value + 1e-12, lo)
                self.assertLessEqual(value - 1e-12, hi)

    def test_semantic_proxy_stays_in_preferred_envelope(self) -> None:
        for index in range(101):
            evidence = motion.semantic_dof_proxy(
                index / 100.0,
                self.contract,
                self.intents,
                self.constraints,
            )
            self.assertEqual(evidence["status"], "PASS")

    def test_contact_and_drift_gates_remain_strict(self) -> None:
        validation = self.contract["validation"]
        self.assertTrue(validation["full_foot_contact_required_every_frame"])
        self.assertTrue(validation["sample_every_frame"])
        self.assertLessEqual(
            float(validation["accepted_endpoint_locked_noise_max"]),
            1e-6,
        )
        self.assertLessEqual(
            float(validation["locked_local_matrix_error_max"]),
            1e-7,
        )
        self.assertLessEqual(
            float(validation["root_horizontal_translation_max"]),
            1e-5,
        )

    def test_releve_scope_is_forbidden(self) -> None:
        authority = self.contract["authority"]
        self.assertTrue(authority["releve_heel_lift_forbidden"])
        self.assertTrue(authority["toe_pivot_motion_forbidden"])
        self.assertEqual(
            self.contract["transition"]["end_pose"],
            "plie",
        )


if __name__ == "__main__":
    unittest.main()
