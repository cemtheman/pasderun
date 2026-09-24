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

## v0.2 — reference observations

`reference_evidence_v0_2.schema.json` and `reference_evidence.py` define evidence for video, still images, prompts and Blend actions. Sources have stable IDs and a reference; media require a **declared** SHA-256, while prompts can refer to text. The validator checks digest syntax but does not load or hash external media. Video and Blend actions use a rational FPS timebase and explicit source frame numbers. Still images and prompts use a static sample. Frames remain in **source time**, without an assumed relationship to MotionSpec frames.

Image and video landmarks use normalized `(u, v)` with `u` increasing right and `v` increasing down in the source image. The source records camera side and whether mirroring is known. Unknown mirroring must not be silently resolved into anatomical left/right. Occluded landmarks have no 2D coordinate. The contract permits 3D coordinates only as **source armature local** observations from a Blend action; these values are not canonical body coordinates or final Rig joint rotations. Prompt evidence is textual. A contact is a confidence-scored hypothesis, not a solved load-bearing support interval. Every annotation identifies whether it was stated, observed, inferred, or supplied by a teacher.

To check a JSON evidence file: `python tools/motion_studio/reference_evidence.py PATH`. The committed prompt example can be checked this way. No image analysis, video processing, landmark detector, MotionSpec conversion, or teacher review is claimed by this checkpoint. A future interpreter may build a MotionSpec from these observations, preserving uncertain and conflicting evidence for human review.

## v0.3 — bounded static geometry probe

`static_pose_v0_3.schema.json` defines one or two wrist targets. Each target starts from the measured shoulder-to-rest-wrist direction, scales that displacement by `reach_fraction`, then adds an offset in declared `(left, up, front)` body axes as a fraction of measured two-link arm reach. `bend_plane` is an explicit geometric pole. `static_pose.py` solves shoulder, elbow and wrist joint centers by two-link geometry, preserving measured segment lengths. It rejects unreachable, straight/folded singular and pole-degenerate targets. No language model supplies bone rotations.

The example `arm_reach_geometry_probe_v0_3.json` is a deliberately modest symmetric arm movement for checking geometry. It is **not** a named ballet pose or an accepted animation. The Blender script `tools/blender/motion_studio/static_pose_preview_v0_3.py` reads the previously generated final-Rig calibration, verifies it against the actual GLB, imports only that final Rig, rotates its upper arm and forearm joints toward the solved landmarks, checks elbow/wrist residuals and writes a `.blend`, front/side PNGs and a JSON report. It does not create keyframes or export a runtime asset.

From a Windows checkout on the v0.3 branch with `build/motion_studio/low_poly_girl_calibration_v0_1.json` already generated:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\static_pose_preview_v0_3.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --target .\tools\motion_studio\examples\arm_reach_geometry_probe_v0_3.json --output .\build\motion_studio\static_pose_v0_3
```

The output reports geometry only; the front and side renders need human inspection. Contact, balance, joint limits, ballet technique, transitions and aesthetics are outside this checkpoint. The static tests use synthetic geometry. Until the actual Blender command and visual gate pass, the v0.3 solver remains a prototype.
