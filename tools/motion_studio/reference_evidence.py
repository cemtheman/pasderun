"""Validate source observations before interpreting them as a MotionSpec.

No image processing, pose estimation, retargeting or motion generation occurs here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from schema_validation import require, shape
from validate import DEFS


SCHEMA = json.loads(Path(__file__).with_name("reference_evidence_v0_2.schema.json").read_text(encoding="utf-8"))


def validate_evidence(data: dict) -> dict:
    shape(data, SCHEMA, "evidence", SCHEMA["$defs"])
    require(set(SCHEMA["$defs"]["landmark"]["enum"]) == set(DEFS["landmark"]["enum"]),
            "schema", "canonical landmark inventory drift")

    sources = data["sources"]
    ids = [source["id"] for source in sources]
    require(len(ids) == len(set(ids)), "sources", "duplicate source id")
    by_id = {source["id"]: source for source in sources}
    timed = {"video", "blend_action"}
    visual = {"video", "image"}
    for source in sources:
        kind = source["kind"]
        require(("timebase" in source) == (kind in timed), source["id"], "timebase required only for timed sources")
        require(("view" in source) == (kind in visual), source["id"], "view required only for images/video")
        require(kind == "prompt" or "sha256" in source, source["id"], "media digest required")

    obs_ids = set()
    samples = set()
    last_frame = {}
    used_sources = set()
    for obs in data["observations"]:
        where = f"observation {obs['id']}"
        require(obs["id"] not in obs_ids, where, "duplicate observation id")
        obs_ids.add(obs["id"])
        source_id = obs["source_id"]
        require(source_id in by_id, where, "unknown source")
        used_sources.add(source_id)
        source = by_id[source_id]
        kind = source["kind"]
        sample = obs["sample"]
        require(("frame" in sample) != ("static" in sample), where, "exactly one of frame or static is required")
        require(("frame" in sample) == (kind in timed), where, "sample type disagrees with source")
        stamp = sample.get("frame", "static")
        require((source_id, stamp) not in samples, where, "duplicate sample")
        samples.add((source_id, stamp))
        if kind in timed:
            base = source["timebase"]
            frame = sample["frame"]
            require(base["first_frame"] <= frame < base["first_frame"] + base["frame_count"], where, "frame outside source")
            require(frame > last_frame.get(source_id, -1), where, "source samples not strictly ordered")
            last_frame[source_id] = frame

        require(kind in visual or not obs["landmarks_2d"], where, "2D landmarks require image/video")
        require(kind == "blend_action" or not obs["landmarks_3d"], where, "3D landmarks require measured Blend/action evidence")
        require(kind != "prompt" or not obs["contact_hypotheses"], where, "prompt contacts belong in textual annotations")
        require(any(obs[k] for k in ("landmarks_2d", "landmarks_3d", "contact_hypotheses", "annotations")), where, "empty observation")

        for key in ("landmarks_2d", "landmarks_3d"):
            names = [point["landmark"] for point in obs[key]]
            require(len(names) == len(set(names)), where, f"duplicate {key} landmark")
        for point in obs["landmarks_2d"]:
            require(("uv" in point) != (point["visibility"] == "occluded"), where, "visible/inferred points need UV; occluded points have none")
        for contact in obs["contact_hypotheses"]:
            if contact["basis"] == "visible":
                require(kind in visual, where, "visible contact requires image/video")
                require(any(point["landmark"] == contact["landmark"] and point["visibility"] == "visible"
                            for point in obs["landmarks_2d"]), where, "visible contact requires visible landmark")
        for annotation in obs["annotations"]:
            if kind == "prompt":
                require(annotation["basis"] in ("stated", "inferred"), where, "prompt text cannot be visually observed")
            else:
                require(annotation["basis"] != "stated", where, "stated basis belongs to prompt")

    require(used_sources == set(ids), "sources", "each source needs an observation")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    evidence = json.loads(args.path.read_text(encoding="utf-8"))
    validate_evidence(evidence)
    print(f"REFERENCE_EVIDENCE=PASS {args.path}")


if __name__ == "__main__":
    main()
