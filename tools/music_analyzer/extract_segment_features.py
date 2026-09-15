#!/usr/bin/env python3
"""Extract Music Analyzer-compatible summary features for a local audio segment."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from analyze import analyze_audio


def _within(items: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    return [item for item in items if 0.0 <= float(item["time"]) <= duration]


def extract_segment(audio_path: Path, start: float, end: float) -> dict[str, Any]:
    if start < 0.0 or end <= start:
        raise ValueError("segment requires 0 <= start < end")

    # Decode only the requested interval to a deterministic PCM WAV. The shared
    # analyzer then supplies the same feature definitions as full-track analysis.
    import subprocess

    with tempfile.TemporaryDirectory() as directory:
        excerpt = Path(directory) / "segment.wav"
        subprocess.run([
            "ffmpeg", "-v", "error", "-ss", f"{start:.6f}", "-t", f"{end - start:.6f}",
            "-i", str(audio_path), "-vn", "-acodec", "pcm_s16le", str(excerpt),
        ], check=True)
        analysis = analyze_audio(excerpt)

    duration = float(analysis["source"]["duration_seconds"])
    energy = _within(analysis["energy"], duration)
    density = _within(analysis["rhythmic_density"], duration)
    sustain = _within(analysis["sustain"]["points"], duration)
    accents = _within(analysis["accents"], duration)

    def mean(items: list[dict[str, Any]], key: str = "value") -> float:
        return round(float(np.mean([item[key] for item in items])), 4) if items else 0.0

    strongest_onset = max((item["strength"] for item in accents), default=0.0)
    return {
        "schema_version": "0.1",
        "source": {"file": audio_path.name, "start_seconds": round(start, 6), "end_seconds": round(end, 6), "duration_seconds": round(duration, 6)},
        "tempo": {"estimated_bpm": analysis["tempo"]["estimated_bpm"], "beat_count": len(analysis["tempo"]["beats"])},
        "onset": {"count": len(accents), "strongest": round(float(strongest_onset), 4)},
        "energy": {"mean": mean(energy), "mean_delta": mean(energy, "delta")},
        "rhythmic_density": {"mean": mean(density)},
        "sustain": {"mean": mean(sustain), "metric": analysis["sustain"]["metric"]}
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.audio.is_file() or args.audio.stat().st_size == 0:
        parser.error(f"audio file is missing or empty: {args.audio}")
    result = extract_segment(args.audio, args.start, args.end)
    payload = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
