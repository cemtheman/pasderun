# Motion Studio v0 — contracts only

`contracts_v0.schema.json` defines seven versioned JSON shapes: canonical human model, MotionSpec, contact, support, rig profile, QA result, and motion asset metadata. Provenance is a shared definition. `validate.py` checks those shapes with Python's standard library and additionally checks timeline order, frame bounds, contact references, frame coverage, support eligibility, and result consistency. Call `validate("motion_spec", data)` after parsing JSON. Run `python -m unittest discover -s tools/motion_studio -p 'test_*.py'` from the repository root.

Frame intervals are **half-open** `[start_frame, end_frame)`. Marker and landmark target frames are within `[0, duration_frames)`. Phases and support intervals each cover the duration in order; an empty support contact list explicitly denotes no modeled support. `support_leg` and `gesture_leg` express intent; support intervals with eligible foot contacts express timed evidence. These may differ during transitions. A `rolling` foot contact can be load bearing; `touch` and `sliding` cannot. No inference of support from a phase label is valid.

Canonical coordinates are `(left, up, front)` relative to the pelvis, divided by standing height. Positive front is body anterior. This is a semantic convention; the final Rig's Blender axes come only from its calibration. Landmark targets are sparse evidence, not a mandatory full pose. Missing targets must never be interpreted as zero positions. Textual constraints record intended choreography, not validated numerical joint limits or an executable solver instruction. v0 supports prompt, image, video, Blend/action, manual, teacher, and hybrid provenance, with external references and optional SHA-256 digests; it never embeds media.

The rig profile contract is intentionally structural. It references the accepted `ballet_rig_calibration_seed_v1.json`, source GLB, and armature. It does not claim measured bone lengths, limits, or a completed calibration. This bridge is for v0.1. Neither the Phase 10 profile nor the accepted reverence is modified. `stumble_recovery_v0.json` is a **semantic example**, with approximate authored phase boundaries; it has not been extracted or verified against the 49-frame local Blend reference. Approval requires a human reviewer, and a QA `pass` alone never implies approval. Asset metadata records the digest of the exact MotionSpec bytes to preserve traceability when produced later.

The contract fixes the body coordinate convention, time indexing, and identity references now. Joint limit values, pose interpolation, IK, contact solve, COM, aesthetics, export format, and runtime binding remain separate future work. Existing Phase 10 canonical skeleton geometry stays reference evidence; its source-rig rotation retarget code is not imported or required by this module. There is no Blender or Godot runtime integration in v0.

## v0.1 — final Rig calibration bridge

`low_poly_girl_rig_profile_v0.json` names the accepted GLB, `Rig`, declared anatomical frame and associated landmark bones. A landmark-to-bone association identifies a candidate joint anchor, **not** a measured landmark location. Heel anchors and precise joint offsets remain unresolved. `rig_calibration_v0_1.schema.json` describes measured rest-pose evidence. `rig_calibration.py` takes the existing Phase 10.6.1 Blender calibration output, verifies its frame policy, all 24 bone transforms and four semantic segments, checks the actual seed and GLB SHA-256, and writes a reduced, versioned evidence artifact. It does not import Blender or infer absent measurements.

On a Windows checkout with the accepted Phase 10 calibration already generated, run from the repository root:

```powershell
python tools/motion_studio/rig_calibration.py --repo . --phase10-calibration build/phase10_6/low_poly_girl_ballet_rig_profile_v1.json --output build/motion_studio/low_poly_girl_calibration_v0_1.json
```

The output is local measured evidence and is not committed by this checkpoint. If the Phase 10 calibration file is absent, the existing `tools/blender/run_ballet_rig_calibration_v1.ps1` produces it in Blender. The Python bridge cannot turn an absent or stale calibration into a PASS. Its `unresolved` list explicitly reserves joint limits, bend planes, contact geometry, landmark offsets, and center of mass for later work. The new tests use synthetic rest geometry to exercise validation paths; they do **not** establish that Blender has been run on the real GLB in this session.
