"""Sample authored MotionSpec states; preserve discrete contact boundaries.

No invented trajectory, landmark interpolation, pose solving or foot locking.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from schema_validation import require, shape
from validate import validate


SCHEMA = json.loads(Path(__file__).with_name("temporal_v0_5.schema.json").read_text(encoding="utf-8"))


def sample_timeline(spec_bytes: bytes, request: dict) -> dict:
    """Bind to exact input bytes and return the declared state at each frame."""
    shape(request, SCHEMA, "temporal", {})
    require(hashlib.sha256(spec_bytes).hexdigest() == request["motion_spec_sha256"],
            "temporal", "MotionSpec digest mismatch")
    spec = json.loads(spec_bytes)
    validate("motion_spec", spec)
    require(spec["motion_id"] == request["motion_id"], "temporal", "motion ID mismatch")
    frames = request["sample_frames"]
    require(frames == sorted(frames), "temporal", "sample frames must be ordered")
    require(frames[-1] < spec["duration_frames"], "temporal", "sample frame outside duration")
    samples = []
    for frame in frames:
        phase = next(p for p in spec["phases"] if p["start_frame"] <= frame < p["end_frame"])
        support = next(s for s in spec["support"] if s["start_frame"] <= frame < s["end_frame"])
        active = [c for c in spec["contacts"] if c["start_frame"] <= frame < c["end_frame"]]
        samples.append({"frame": frame, "phase_id": phase["id"],
                        "support_contact_ids": list(support["contact_ids"]),
                        "active_contact_ids": [c["id"] for c in active],
                        "marker_ids": [m["id"] for m in spec["markers"] if m["frame"] == frame],
                        "landmark_targets": [t for t in spec["landmark_targets"] if t["frame"] == frame]})
    return {"schema_version": "0.5.0", "motion_id": spec["motion_id"],
            "motion_spec_sha256": request["motion_spec_sha256"], "samples": samples,
            "limits": "Declared state only; no interpolated pose, physical contact or balance claim"}
