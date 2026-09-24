"""Qualitative, joint-center checks for preparation to second-position arms.

Only checks relations visible in user-provided reference. No pose authoring.
"""

from __future__ import annotations

from static_pose import dot


def evaluate_port_de_bras(poses, anatomical_frame):
    """Return explicit checks on start, intermediate and end arm solutions.

    ``poses`` must have start, middle and end, each with solved left/right arms.
    Unknown anatomy (hands, scapula, joint limits) remains untested.
    """
    checks = []
    left, up, front = (anatomical_frame[key] for key in ("left", "up", "front"))

    def record(name, passed, evidence):
        checks.append({"name": name, "status": "pass" if passed else "fail", "evidence": evidence})

    for side, sign in (("left", 1), ("right", -1)):
        arms = [poses[stage]["arms"][side] for stage in ("start", "middle", "end")]
        start, middle, end = arms
        coord = lambda arm, joint, axis: dot(arm[joint], axis)
        # Preparatory hands turn toward center rather than pointing outside elbows.
        start_elbow = sign*coord(start, "elbow", left)
        start_wrist = sign*coord(start, "wrist", left)
        record(f"{side}_preparatory_wrist_inside_elbow", start_wrist < start_elbow,
               f"lateral elbow={start_elbow:.6f} wrist={start_wrist:.6f}")
        outward = [sign*coord(arm, "wrist", left) for arm in arms]
        # The en_avant waypoint can bring hands slightly toward center before
        # they open to second; require the final opening, not monotonic travel.
        record(f"{side}_wrist_opens_outward", outward[2] > outward[1] and outward[2] > outward[0],
               f"lateral wrist start/middle/end={outward}")
        for stage, arm in (("middle", middle), ("end", end)):
            shoulder_up = coord(arm, "shoulder", up)
            elbow_up = coord(arm, "elbow", up)
            wrist_up = coord(arm, "wrist", up)
            record(f"{side}_{stage}_elbow_line", shoulder_up > elbow_up > wrist_up,
                   f"up shoulder={shoulder_up:.6f} elbow={elbow_up:.6f} wrist={wrist_up:.6f}")
        shoulder_front = coord(end, "shoulder", front)
        wrist_front = coord(end, "wrist", front)
        record(f"{side}_second_position_anterior", wrist_front > shoulder_front,
               f"front shoulder={shoulder_front:.6f} wrist={wrist_front:.6f}")

    for name in ("shoulder_depression", "hand_shape", "scapula_control", "teacher_approval"):
        checks.append({"name": name, "status": "not_run", "evidence": "not determined from solved arm joint centers"})
    return {"status": "fail" if any(c["status"] == "fail" for c in checks) else "not_run",
            "checks": checks, "limits": "Qualitative geometry only; no ballet acceptance from this result"}
