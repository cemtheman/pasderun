# Music Analyzer v0.1

Deterministic offline DSP analysis for Pas de Run. It decodes audio through
`ffmpeg`, reads metadata through `ffprobe`, and uses NumPy/SciPy for spectral
flux, tempo, energy, onset density, stability, boundary novelty, and intensity
candidates.

The `sustain` value is a proxy, not a musicological label. It is the inverse of
a blend of local spectral attack activity (70%) and energy variability (30%).

Run from the repository root:

```sh
python tools/music_analyzer/analyze.py assets/audio/graceful_opening.mp3 \
  --output data/music/graceful_opening.analysis.json
```

Focused tests:

```sh
python -m unittest discover -s tools/music_analyzer -p 'test_*.py'
```
