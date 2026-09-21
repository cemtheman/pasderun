from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools" / "ballet_motion"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import foundation_motion_10_7_2 as motion  # noqa: E402


class Phase1072FoundationMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(
            (REPO / "assets" / "ballet_motion" / "foundation_motion_en_avant_to_second_v1.json").read_text(
                encoding="utf-8"
            )
        )
        cls.intents = json.loads(
            (REPO / "assets" / "ballet_motion" / "foundation_pose_intents_v1.json").read_text(
                encoding="utf-8"
            )
        )
        cls.constraints = json.loads(
            (REPO / "assets" / "ballet_motion" / "anatomical_constraints_v1.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_and_frame_range(self) -> None:
        motion.validate_contract(self.contract)
        self.assertEqual(motion.frame_end(self.contract), 61)
        self.assertEqual(motion.normalized_time(1, self.contract), 0.0)
        self.assertEqual(motion.normalized_time(61, self.contract), 1.0)

    def test_role_progress_is_bounded_monotone_and_exact_at_endpoints(self) -> None:
        previous = {role: 0.0 for role in motion.ROLE_ORDER}
        for index in range(1001):
            t = index / 1000.0
            for role in motion.ROLE_ORDER:
                value = motion.windowed_progress(
                    t, self.contract["joint_windows"][role]
                )
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)
                self.assertGreaterEqual(value + 1e-12, previous[role])
                previous[role] = value

        for role in motion.ROLE_ORDER:
            self.assertEqual(
                motion.windowed_progress(0.0, self.contract["joint_windows"][role]),
                0.0,
            )
            self.assertEqual(
                motion.windowed_progress(1.0, self.contract["joint_windows"][role]),
                1.0,
            )

    def test_proximal_to_distal_window_order(self) -> None:
        windows = self.contract["joint_windows"]
        starts = [windows[role]["start"] for role in motion.ROLE_ORDER]
        ends = [windows[role]["end"] for role in motion.ROLE_ORDER]
        widths = [
            windows[role]["end"] - windows[role]["start"]
            for role in motion.ROLE_ORDER
        ]
        self.assertEqual(starts, sorted(starts))
        self.assertEqual(ends, sorted(ends))
        for proximal, distal in zip(widths, widths[1:]):
            self.assertGreaterEqual(proximal, distal)

    def test_adjacent_role_progress_lag_stays_tightly_coupled(self) -> None:
        maximum = float(
            self.contract["validation"]["maximum_adjacent_role_progress_lag"]
        )
        for index in range(1001):
            t = index / 1000.0
            progress = {
                role: motion.windowed_progress(
                    t,
                    self.contract["joint_windows"][role],
                )
                for role in motion.ROLE_ORDER
            }
            for proximal, distal in zip(
                motion.ROLE_ORDER,
                motion.ROLE_ORDER[1:],
            ):
                lag = progress[proximal] - progress[distal]
                self.assertGreaterEqual(lag + 1e-12, 0.0)
                self.assertLessEqual(lag, maximum + 1e-12)

    def test_bounded_scalar_interpolation_is_exact_and_no_overshoot(self) -> None:
        for start, end in ((-12.5, 18.0), (20.0, -7.0), (0.0, 0.0)):
            self.assertEqual(
                motion.interpolate_bounded_scalar(start, end, 0.0),
                start,
            )
            self.assertEqual(
                motion.interpolate_bounded_scalar(start, end, 1.0),
                end,
            )
            minimum = min(start, end)
            maximum = max(start, end)
            previous = None
            for index in range(101):
                p = index / 100.0
                value = motion.interpolate_bounded_scalar(start, end, p)
                self.assertGreaterEqual(value + 1e-12, minimum)
                self.assertLessEqual(value - 1e-12, maximum)
                if previous is not None:
                    if end >= start:
                        self.assertGreaterEqual(value + 1e-12, previous)
                    else:
                        self.assertLessEqual(value - 1e-12, previous)
                previous = value

    def test_semantic_proxy_never_leaves_preferred_envelope(self) -> None:
        for index in range(101):
            evidence = motion.semantic_dof_proxy(
                index / 100.0,
                self.contract,
                self.intents,
                self.constraints,
            )
            self.assertEqual(evidence["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
