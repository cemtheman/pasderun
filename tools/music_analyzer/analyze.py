#!/usr/bin/env python3
"""Deterministic offline musical feature extraction for Pas de Run."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from scipy.ndimage import gaussian_filter1d, uniform_filter1d
from scipy.signal import find_peaks


SCHEMA_VERSION = "0.1"
ANALYSIS_SAMPLE_RATE = 22_050
FRAME_SIZE = 2_048
HOP_SIZE = 512
SUMMARY_STEP_SECONDS = 0.25


def _run_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def _metadata(audio_path: Path) -> dict[str, Any]:
    payload = _run_json([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,sample_rate,channels",
        "-of", "json", str(audio_path),
    ])
    audio_stream = next(stream for stream in payload["streams"] if stream["codec_type"] == "audio")
    return {
        "duration_seconds": float(payload["format"]["duration"]),
        "sample_rate": int(audio_stream["sample_rate"]),
        "channels": int(audio_stream["channels"]),
    }


def _decode_mono(audio_path: Path) -> np.ndarray:
    result = subprocess.run([
        "ffmpeg", "-v", "error", "-i", str(audio_path), "-vn",
        "-ac", "1", "-ar", str(ANALYSIS_SAMPLE_RATE), "-f", "f32le", "-",
    ], check=True, capture_output=True)
    return np.frombuffer(result.stdout, dtype="<f4").astype(np.float64)


def _normalize(values: np.ndarray, percentile: float = 99.0) -> np.ndarray:
    values = np.maximum(np.asarray(values, dtype=np.float64), 0.0)
    scale = float(np.percentile(values, percentile)) if values.size else 0.0
    if scale <= np.finfo(float).eps:
        return np.zeros_like(values)
    return np.clip(values / scale, 0.0, 1.0)


def _frames(samples: np.ndarray) -> np.ndarray:
    if samples.size < FRAME_SIZE:
        samples = np.pad(samples, (0, FRAME_SIZE - samples.size))
    count = 1 + (samples.size - FRAME_SIZE) // HOP_SIZE
    shape = (count, FRAME_SIZE)
    strides = (samples.strides[0] * HOP_SIZE, samples.strides[0])
    return np.lib.stride_tricks.as_strided(samples, shape=shape, strides=strides)


def _frame_features(samples: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    framed = _frames(samples)
    window = np.hanning(FRAME_SIZE)
    spectra = np.abs(np.fft.rfft(framed * window, axis=1))
    log_spectra = np.log1p(10.0 * spectra)
    flux = np.maximum(np.diff(log_spectra, axis=0, prepend=log_spectra[:1]), 0.0).sum(axis=1)
    rms = np.sqrt(np.mean(np.square(framed), axis=1))
    times = (np.arange(framed.shape[0]) * HOP_SIZE + FRAME_SIZE / 2) / ANALYSIS_SAMPLE_RATE
    return times, _normalize(flux), _normalize(rms)


def _onsets(frame_times: np.ndarray, onset_envelope: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    smoothed = gaussian_filter1d(onset_envelope, sigma=1.0)
    distance = max(1, round(0.12 * ANALYSIS_SAMPLE_RATE / HOP_SIZE))
    threshold = max(0.08, float(np.percentile(smoothed, 60)))
    peaks, _ = find_peaks(smoothed, height=threshold, prominence=0.025, distance=distance)
    return frame_times[peaks], smoothed[peaks]


def _tempo_and_beats(frame_times: np.ndarray, onset_envelope: np.ndarray) -> tuple[float, np.ndarray]:
    rate = ANALYSIS_SAMPLE_RATE / HOP_SIZE
    centered = onset_envelope - np.mean(onset_envelope)
    correlation = np.correlate(centered, centered, mode="full")[centered.size - 1:]
    minimum_lag = max(1, math.floor(60.0 * rate / 180.0))
    maximum_lag = min(correlation.size - 2, math.ceil(60.0 * rate / 70.0))
    lags = np.arange(minimum_lag, maximum_lag + 1)
    lag_scores = correlation[lags] * np.sqrt((60.0 * rate / lags) / 120.0)
    peak_lag = int(lags[int(np.argmax(lag_scores))])
    left, center, right = correlation[peak_lag - 1:peak_lag + 2]
    denominator = left - 2.0 * center + right
    offset = 0.5 * (left - right) / denominator if abs(denominator) > 1e-12 else 0.0
    refined_lag = peak_lag + float(np.clip(offset, -0.5, 0.5))
    bpm = 60.0 * rate / refined_lag
    period = 60.0 / bpm

    phases = np.linspace(0.0, period, 200, endpoint=False)
    best_phase = 0.0
    best_score = -math.inf
    for phase in phases:
        grid = np.arange(phase, frame_times[-1] + period, period)
        indices = np.clip(np.rint(grid * rate).astype(int), 0, onset_envelope.size - 1)
        score = float(onset_envelope[indices].sum())
        if score > best_score:
            best_score = score
            best_phase = float(phase)
    beats = np.arange(best_phase, frame_times[-1] + period, period)
    return bpm, beats


def _summary_grid(duration: float) -> np.ndarray:
    return np.arange(0.0, duration + 1e-9, SUMMARY_STEP_SECONDS)


def _sample_to_grid(frame_times: np.ndarray, values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    return np.interp(grid, frame_times, values, left=float(values[0]), right=float(values[-1]))


def _select_candidates(times: np.ndarray, strengths: np.ndarray, *, distance_seconds: float,
                       max_count: int, minimum: float = 0.1) -> list[dict[str, float]]:
    distance = max(1, round(distance_seconds / SUMMARY_STEP_SECONDS))
    peaks, _ = find_peaks(strengths, height=minimum, distance=distance)
    ranked = sorted(peaks, key=lambda index: (-strengths[index], times[index]))[:max_count]
    return [
        {"time": round(float(times[index]), 3), "strength": round(float(strengths[index]), 4)}
        for index in sorted(ranked, key=lambda index: times[index])
    ]


def analyze_audio(audio_path: Path) -> dict[str, Any]:
    metadata = _metadata(audio_path)
    samples = _decode_mono(audio_path)
    frame_times, onset_envelope, frame_energy = _frame_features(samples)
    onset_times, onset_strengths = _onsets(frame_times, onset_envelope)
    bpm, beats = _tempo_and_beats(frame_times, onset_envelope)

    grid = _summary_grid(metadata["duration_seconds"])
    energy = gaussian_filter1d(_sample_to_grid(frame_times, frame_energy, grid), sigma=1.0)
    energy = _normalize(energy)
    energy_delta = np.gradient(energy, SUMMARY_STEP_SECONDS)
    energy_delta = np.clip(energy_delta, -1.0, 1.0)

    density_counts = np.zeros_like(grid)
    half_window = 1.0
    for index, time in enumerate(grid):
        density_counts[index] = np.count_nonzero(
            (onset_times >= time - half_window) & (onset_times <= time + half_window)
        )
    density = _normalize(density_counts, percentile=100.0)

    attack_activity = gaussian_filter1d(_sample_to_grid(frame_times, onset_envelope, grid), sigma=2.0)
    local_variability = np.abs(energy - uniform_filter1d(energy, size=9, mode="nearest"))
    sustain = np.clip(1.0 - (0.7 * _normalize(attack_activity) + 0.3 * _normalize(local_variability)), 0.0, 1.0)

    look = max(1, round(2.0 / SUMMARY_STEP_SECONDS))
    boundary_novelty = np.zeros_like(grid)
    feature_matrix = np.column_stack((energy, density, sustain))
    for index in range(look, grid.size - look):
        before = feature_matrix[index - look:index].mean(axis=0)
        after = feature_matrix[index:index + look].mean(axis=0)
        boundary_novelty[index] = np.linalg.norm(after - before)
    boundary_novelty = _normalize(gaussian_filter1d(boundary_novelty, sigma=1.0))

    positive_delta = _normalize(np.maximum(energy_delta, 0.0))
    intensity = _normalize(0.55 * energy + 0.25 * density + 0.20 * positive_delta)

    accents = sorted(
        ({"time": round(float(time), 3), "strength": round(float(strength), 4)}
         for time, strength in zip(onset_times, onset_strengths, strict=True)),
        key=lambda item: item["time"],
    )

    def series(values: np.ndarray, include_delta: bool = False) -> list[dict[str, float]]:
        output: list[dict[str, float]] = []
        for index, time in enumerate(grid):
            item = {"time": round(float(time), 3), "value": round(float(values[index]), 4)}
            if include_delta:
                item["delta"] = round(float(energy_delta[index]), 4)
            output.append(item)
        return output

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "file": audio_path.name,
            "duration_seconds": round(metadata["duration_seconds"], 6),
            "sample_rate": metadata["sample_rate"],
            "channels": metadata["channels"],
            "analysis_sample_rate": ANALYSIS_SAMPLE_RATE,
        },
        "tempo": {
            "estimated_bpm": round(bpm, 3),
            "beats": [round(float(time), 3) for time in beats if time <= metadata["duration_seconds"]],
        },
        "accents": accents,
        "energy": series(energy, include_delta=True),
        "rhythmic_density": series(density),
        "sustain": {
            "metric": "Inverse blend of normalized local spectral attack activity (70%) and energy variability (30%); higher values indicate a steadier, less attack-heavy signal.",
            "points": series(sustain),
        },
        "boundaries": _select_candidates(grid, boundary_novelty, distance_seconds=3.0, max_count=24, minimum=0.12),
        "climax_candidates": _select_candidates(grid, intensity, distance_seconds=4.0, max_count=16, minimum=0.2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.audio.is_file() or args.audio.stat().st_size == 0:
        parser.error(f"audio file is missing or empty: {args.audio}")
    analysis = analyze_audio(args.audio)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
