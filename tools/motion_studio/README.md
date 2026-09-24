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

The example `arm_reach_geometry_probe_v0_3.json` is a deliberately modest symmetric arm movement for checking geometry. After the first visual review showed a pronounced forward elbow kink, its explicit bend plane was changed to body-down and its target moved closer to the rest wrist. It is **not** a named ballet pose or an accepted animation. The Blender script `tools/blender/motion_studio/static_pose_preview_v0_3.py` reads the previously generated final-Rig calibration, verifies it against the actual GLB, imports only that final Rig, rotates its upper arm and forearm joints toward the solved landmarks, checks elbow/wrist residuals and writes a `.blend`, matched rest/solved front and side PNGs and a JSON report. It does not create keyframes or export a runtime asset.

From a Windows checkout on the v0.3 branch with `build/motion_studio/low_poly_girl_calibration_v0_1.json` already generated:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\static_pose_preview_v0_3.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --target .\tools\motion_studio\examples\arm_reach_geometry_probe_v0_3.json --output .\build\motion_studio\static_pose_v0_3
```

The output reports geometry only; the front and side renders need human inspection. Contact, balance, joint limits, ballet technique, transitions and aesthetics are outside this checkpoint. The static tests use synthetic geometry. Until the actual Blender command and visual gate pass, the v0.3 solver remains a prototype.

## v0.4 — rest-foot contact and support diagnostic

`contact_support_v0_4.schema.json` records explicitly sourced, armature-local foot sole points, active contacts, the calibrated body frame, the ground plane and an allowed shared height spread. `contact_support.py` checks each active patch and computes its projected convex hull, the combined support polygon and the vertical root shift required to align its lowest point with the ground. It rejects collinear patches, mismatched calibration and contact sets whose heights cannot share that plane. It does not move the root horizontally or infer contacts from choreography.

An optional center of mass measurement produces a signed support-edge margin. Without that evidence the result is `UNKNOWN_NO_COM`; a declared human estimate yields `INDICATIVE_ESTIMATE`, never a measured balance verdict. A support polygon alone cannot establish balance or dynamic stability.

The Blender diagnostic `tools/blender/motion_studio/rest_foot_contact_v0_4.py` imports only the final GLB and extracts candidate rest-pose sole outlines from vertices weighted to its Foot/Toes bones. It writes `foot_patches.json`, `report.json` and `support_top.svg`. The mesh band is candidate contact geometry for visual review, not a validated pressure footprint or a ballet pose. Run from the repository root on Windows after generating the v0.1 calibration:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\rest_foot_contact_v0_4.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --output .\build\motion_studio\contact_support_v0_4
```

Static tests exercise the contract and synthetic support geometry. The real Blender extraction, the shape of the sole outlines and ground suitability require the local Blender run and human review. No animation, COM estimation, Godot integration or production export is part of v0.4.

## v0.5 — authored timeline sampling

`temporal_v0_5.schema.json` defines a request tied to the SHA-256 digest of exact MotionSpec bytes, a motion ID and ordered frame indices. `temporal.py` validates the existing MotionSpec and samples its declared phase, active contacts, load-bearing support, markers and explicit landmark targets at each requested frame. Half-open intervals preserve exact handoff boundaries; a support gap stays empty. The 49-frame stumble example checks the boundary behavior as semantic test evidence, not as a verified reconstruction of its Blender reference.

The sampler does **not** interpolate missing landmarks, infer physical foot contact, generate poses, keyframes or animation, or claim temporal smoothness. Continuous trajectory construction and transition compatibility require separate geometric evidence and review. Run the focused and existing tests with `python -m unittest discover -s tools/motion_studio -p 'test_*.py'`. This checkpoint is static Python only and requires no Blender run.

## v0.5 arm transition geometry probe

`arm_transition_v0_5.schema.json` embeds two already versioned v0.3 static arm target specifications with identical arm sides and bend planes. `arm_transition.py` interpolates only their declared reach fractions and body-relative offsets using smoothstep, then solves two-link geometry independently at **every integer frame**. A changed bend pole requires separate authored evidence and is rejected. The committed 17-frame example raises both wrist targets modestly; this probe has no choreographic name or approval.

`tools/blender/motion_studio/arm_transition_preview_v0_5.py` imports the final Rig, applies each geometrically solved frame, keys both upper arm and forearm rotations, then re-evaluates all keyed frames and checks wrist/elbow residuals. It saves a `.blend`, a JSON report and front/side PNGs for first, middle and last frames. The Blender file is a local review artifact; it is not exported to Godot or the approved motion library. Run from a Windows checkout with the v0.1 calibration already generated:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\arm_transition_preview_v0_5.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --target .\tools\motion_studio\examples\arm_transition_geometry_probe_v0_5.json --output .\build\motion_studio\arm_transition_v0_5
```

The Python tests cover synthetic endpoints, monotone wrist motion, pole continuity and invalid requests. A real Blender execution and human review are still required; this arm-only experiment does not establish foot contact, balance, joint limits, or ballet quality. The earlier MotionSpec timeline sampler remains a separate semantic reader and does not claim these geometric targets as MotionSpec evidence.

## v0.6 — preparatory to second-position reference evidence and geometric checks

`examples/port_de_bras_reference_v0_6.json` records the user's three-stage description and panels of their AI-generated front/side composite as separate observations. Every panel points to the same source-image SHA-256; the image itself is not included in the repository. These are qualitative illustrations, not timed video frames, anatomical coordinates or teacher validation. The initial arm-lift geometry probe is **not** reclassified as port de bras.

`port_de_bras_qa.py` checks relationships visible in that reference on *supplied* solved shoulder, elbow and wrist joint centers: preparatory wrists inside elbows, wrists opening from en_avant to second, shoulder–elbow–wrist descending lines at middle/end and anterior wrists at the end. The en_avant waypoint may move the wrists slightly inward before the final opening. This check has no guessed bone Euler angles or numeric ballet-angle thresholds. Shoulder depression, hand shape, scapular control and teacher approval are explicitly `not_run`; an all-passing geometry result remains `not_run` overall rather than motion approval. The earlier arm-lift probe fails the preparatory check as expected. Validate evidence with `python tools/motion_studio/reference_evidence.py tools/motion_studio/examples/port_de_bras_reference_v0_6.json` and run unit tests with `python -m unittest discover -s tools/motion_studio -p 'test_*.py'`.

This checkpoint does not solve the new ballet sequence. A future pose solver must work from observed landmark relationships and final-Rig calibration, followed by Blender previews and human/teacher review. The generated illustration alone does not provide defensible 3D elbow positions, hand articulation or actual timing.

## v0.6.1 — accepted Phase 10 landmark reference bridge

The trusted Phase 10.6.5 canonical foundation output contains `bras_bas`, `en_avant`, and `second` landmark poses. `accepted_arm_reference.py` reads an **existing generated profile as evidence**. It verifies its Phase 10 geometry gates and source GLB digest, extracts only shoulder/elbow/wrist/hand body-relative landmarks, and scales coordinates by this Rig's measured standing height. The resulting `accepted_arm_reference_v0_6.schema.json` contract preserves the digest of the exact input profile. It never imports or runs any old source-rig retargeting or animation-authoring code. These three static poses remain distinct from the new user's generated visual reference and do not confer motion approval.

An optional review compares `bras_bas → en_avant → second` with the v0.6 qualitative arm checks. Failure is reported as failure; all passing geometric relations still leave teacher approval `not_run`. If the already-generated `build/phase10_6/low_poly_girl_canonical_pose_solver_v1.json` exists locally, the read-only bridge may be run from the repository root:

```powershell
python .\tools\motion_studio\accepted_arm_reference.py --source .\build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --output .\build\motion_studio\accepted_arm_reference_v0_6.json --review-output .\build\motion_studio\accepted_arm_review_v0_6.json
```

If the source profile is absent, the bridge cannot claim a real-data result. The bridge is tested on synthetic profiles; a real output and visual interpretation still require local evidence. No Blender run, GLB export, runtime integration or changes to accepted Phase 10 assets occur in this checkpoint.

### Read-only final-Rig visual check

`accepted_arm_visual.py` converts the three existing body-relative poses back to local joint targets with the measured final-Rig frame and standing height. It rejects a stale GLB digest, missing joints or arm segment lengths inconsistent with calibration. The Blender preview also regenerates the accepted reference from the **exact Phase 10 source bytes** and requires it to match the supplied JSON. It resets the final Rig to rest between poses, applies the existing geometric arm joint alignment, checks elbow and wrist residuals and renders front/side views. The saved Blend has only the final static pose; no keyframes or export are generated. Neither the accepted Phase 10 source nor the character GLB is changed.

Run on the Windows checkout after creating `accepted_arm_reference_v0_6.json` and retaining the two Phase 10 inputs:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\accepted_arm_visual_v0_6.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --reference .\build\motion_studio\accepted_arm_reference_v0_6.json --source-profile .\build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json --output .\build\motion_studio\accepted_arm_visual_v0_6
```

The six PNGs show whether accepted joint-center geometry produces a readable silhouette on this mesh. A numerical geometry PASS does not override the earlier `second` elbow-line QA failure or count as ballet acceptance. Human review of both views and any rig/mesh limitations is necessary before choosing a corrective target; no new limb angles are inferred by this visual check.

The first real Blender visual pass placed elbow and wrist joint centers within tolerance but left the hands uncontrolled, visibly crossing in preparatory and en avant and drooping in second. The source profile defines a hand endpoint one measured hand-bone length beyond each wrist. The preview now additionally rejects mismatched hand lengths and aims the actual final-Rig hand bone tail at that accepted endpoint, with a reported residual. This is a bounded correction of the preview; it does not repair the high elbow in second or grant choreography approval.

The subsequent real Blender visual pass confirmed accurate elbow/wrist/hand-tip geometry, while `reviews/accepted_arm_visual_review_v0_6.json` records the unresolved mesh hand overlap and second-position elbow line. It pins the exact local report and six renders by SHA-256 without committing generated images. Its `needs_revision` result is an assistant visual observation; no human or ballet-teacher acceptance is asserted. The Phase 10 landmark reference remains evidence, not an approved Motion Studio asset.

After the user confirmed the hands still intersect visually, the same preview gained a read-only **final-mesh projection** diagnostic. For each pose it samples evaluated skinned vertices predominantly weighted to the actual Hand bones or descendants, then measures the lateral gap between the two hand silhouettes in the front view. A negative gap establishes projected overlap, but cannot by itself establish physical 3D penetration because one hand may be in front of the other. Missing skin evidence or a changed vertex inventory aborts rather than reporting a false measurement. This diagnostic does not alter pose targets; its output provides measurable mesh clearance evidence for a later contact-aware target solve.

The measured real final-Rig gaps were −0.25650954 for `bras_bas`, −0.18994057 for `en_avant`, and +1.21331245 for `second`, in armature units. The exact local diagnostic report has SHA-256 `c375d62de2ac0facd012bf5580a96ef6a25c17a5b14d6644be67e4254b9500be`. This is frontal projection evidence, not a measured 3D intersection volume.

`hand_clearance_candidate.py` and `tools/blender/motion_studio/hand_clearance_candidate_v0_6.py` produce **separate unapproved static candidates** for the two overlapping poses. The Blender script checks the source and reference digests, remeasures the baseline gap on the current final mesh, then moves each wrist outward by the measured half-overlap and repeats only if the evaluated skin still overlaps in the front projection. At every trial it geometrically re-solves the elbow with measured link lengths and the original bend direction, and preserves the wrist-to-hand direction. No Euler angles, original profiles, accepted reverence, keyframes or runtime assets are changed. It stops with an error if the geometry cannot be cleared within the bounded search.

From the Windows checkout after running the read-only mesh diagnostic, run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\hand_clearance_candidate_v0_6.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --reference .\build\motion_studio\accepted_arm_reference_v0_6.json --source-profile .\build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json --measurement .\build\motion_studio\accepted_arm_mesh_diagnostic_v0_6\report.json --output .\build\motion_studio\hand_clearance_candidate_v0_6
```

Inspect its four front/side previews even if the numerical projection gap becomes positive. A positive frontal gap does not establish clean ballet port de bras, hand or torso contact safety, or motion transition quality. The second-position elbow defect remains outside this hand-clearance experiment.

The real Blender hand-clearance candidate reached +0.00230336 (`bras_bas`) and +0.00482005 (`en_avant`) armature units of frontal hand separation. Human review found the preparation improved and identified one remaining **downward elbow kink in the en avant side view**. `en_avant_outward_elbow_v0_6.py` reuses the same measured wrist clearance and changes only en avant's geometric elbow bend pole to declared body-outward, a direction already specified in the supplied ballet description. It recalculates each arm from the measured link lengths, compares projected side-view bend before/after, and checks final-mesh hand clearance again. This is an unapproved pose candidate, not a change to the accepted Phase 10 reference or reverence.

Run after creating `build/motion_studio/hand_clearance_candidate_v0_6/report.json`:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\en_avant_outward_elbow_v0_6.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --reference .\build\motion_studio\accepted_arm_reference_v0_6.json --source-profile .\build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json --clearance-report .\build\motion_studio\hand_clearance_candidate_v0_6\report.json --output .\build\motion_studio\en_avant_outward_elbow_v0_6
```

Review the resulting **two** front and side renders. The script aborts if it cannot reproduce the earlier hand clearance, if that clearance is lost, or if the projected side-view bend does not decrease. A smaller numerical bend still requires human review of the visible mesh and arm line.

### Second-position descending elbow candidate

The accepted Phase 10 second-position wrist and hand landmarks remain fixed, but its elbow rises above the shoulder in the front render. `second_elbow_line.py` uses the two measured arm lengths to put the elbow halfway between shoulder and wrist height on the reachable elbow circle. It chooses the intersection nearest the accepted elbow, without changing the existing arm lengths or the other two poses. This is an independently reviewable static candidate; it does not alter the accepted source profile.

With the existing calibration and accepted reference in the Windows checkout, run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\second_elbow_line_v0_6.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --reference .\build\motion_studio\accepted_arm_reference_v0_6.json --source-profile .\build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json --output .\build\motion_studio\second_elbow_line_v0_6
```

Inspect `second_descending_front.png`, `second_descending_side.png`, and `report.json`. The Blender preview checks source digests, solved joint residuals, descending elbow height, anterior elbow position, hand endpoints and the evaluated frontal hand-mesh gap. It does not validate the appearance of the resulting arm contour, three-dimensional collision, transitions or ballet technique. The saved Blend has only this static final-Rig pose, with no keyframes or GLB export.

The real `second_descending_side.png` exposed an additional defect: fixing the wrist at the accepted Phase 10 location while lowering the elbow forces the forearm back toward the torso. Its measured elbow was 0.09514467 armature units anterior to the shoulder, but the wrist lay behind the elbow. The descending preview is retained only as evidence of this failed candidate.

`second_forward_line_v0_6.py` searches reachable wrist positions slightly forward and, if necessary, slightly inward. It reconstructs the mid-height elbow from the **original measured upper-arm and forearm lengths**, carries the accepted wrist-to-hand vector along with the wrist, and requires both shoulder-to-elbow and elbow-to-wrist to progress forward in the side view. Bounded side-view turn and three-dimensional elbow bend are provisional shape constraints, not ballet standards. It renders only the second pose, leaving the preparatory and en avant candidates untouched:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\second_forward_line_v0_6.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --reference .\build\motion_studio\accepted_arm_reference_v0_6.json --source-profile .\build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json --output .\build\motion_studio\second_forward_line_v0_6
```

Review `second_forward_front.png`, `second_forward_side.png` and `report.json` before accepting any shape change. No source assets, keyframes or runtime motions are changed.

The real second-forward preview improved the side line, but its measured upper-arm-relative flexion still pointed **outward**. `elbow_flexion.py` introduces a reusable signed flexion guard: subtract the portion of the forearm along the current upper arm, then require the remaining bend component to point toward the declared anatomical inward cue. It rotates with the upper arm instead of banning a fixed world-space up/down direction. A singular straight arm and an outward bend are rejected. The en avant outward-elbow probe is checked against the same guard. Earlier generated reports remain historical evidence; no accepted reference is rewritten.

The second-position search now considers only inward-flexing candidates, retains its length and front/side constraints, and writes separate review outputs. On the Windows checkout, run the updated `second_forward_line_v0_6.py` into a new directory:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\second_forward_line_v0_6.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --reference .\build\motion_studio\accepted_arm_reference_v0_6.json --source-profile .\build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json --output .\build\motion_studio\second_inward_line_v0_6
```

Review `second_inward_front.png`, `second_inward_side.png` and `report.json`. This signed body cue establishes the **side of the bend**, not a measured anatomical hinge axis or range. The v0.1 calibration explicitly marks joint limits and bend planes unresolved. Rig-local hinge enforcement needs an independently measured local axis and shoulder/upper-arm orientation; this candidate must not be labeled anatomy approved.

### Three-pose path geometry probe

`reviews/port_de_bras_static_feedback_v0_6.json` pins the final local static report and front/side render digests. The user visually liked the second-position inward candidate; preparatory and en avant feedback is recorded separately without claiming a teacher's approval. These observations are inputs to the next **arm-only path probe**, not an approved ballet motion.

`port_de_bras_path.py` uses 49 review samples with exact static poses at samples 1, 25 and 49. It eases wrist targets between the poses and re-solves every elbow from the measured upper-arm and forearm lengths. A direction-normalized hand vector retains hand-bone length, and each frame must keep an inward signed flexion. The Blender preview keys each sample, checks evaluated elbow, wrist and hand-tip residuals, measures the frontal skinned-hand gap at **every** playback frame, and renders front/side samples at 1, 13, 25, 37 and 49. The grid and preview frame rate are diagnostic choices; they are not observed movement timing.

After generating the three previously described local static reports, run from the Windows checkout:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\port_de_bras_path_preview_v0_6.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --reference .\build\motion_studio\accepted_arm_reference_v0_6.json --source-profile .\build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json --clearance-report .\build\motion_studio\hand_clearance_candidate_v0_6\report.json --en-avant-report .\build\motion_studio\en_avant_outward_elbow_v0_6\report.json --second-report .\build\motion_studio\second_inward_line_v0_6\report.json --output .\build\motion_studio\port_de_bras_path_probe_v0_6
```

Inspect `report.json` and the five pairs of preview PNGs. The script reports frontal hand overlap as a failed review gate rather than accepting a numerically accurate pose path. Positive frontal separation alone cannot prove that arms avoid the torso or each other in three dimensions. It exports no GLB and modifies no accepted or production motion.

### Guide correction: first position before a new path

The first actual 49-frame Blender run returned `PATH_PROBE_FRONT_HAND_OVERLAP`: 11 frames, numbered 7–17, showed negative projected hand separation, worst −0.01256776 armature units at frame 13. The user-provided *Ballet Positions Catalog & Guide* (PDF SHA-256 `2d6321bf92dd97014fb86555bc30426772e9a34e0527e7bf397339fa3648793d`) also distinguishes **Bra Bas** at hip level, **first arm position** with rounded arms and hands near the navel, and **second arm position** slightly ahead of the shoulders. The existing Phase 10 `en_avant` rendered at chest level and does not meet that first-position description. Frame 37 was merely a diagnostic midpoint and did not yield a readable opening. That path is rejected; its exact endpoint source data remain unchanged.

`first_position_candidate.py` therefore creates a **new unapproved static waypoint**. Its wrist elevation is midway between the reviewed Bra Bas wrist and the previously high en avant wrist, and its forward displacement is midway between them. Its lateral hand clearance begins at the measured en avant wrist location. The elbow is solved from calibrated arm lengths with an outward elbow pole and the inward flexion guard. This arithmetic midpoint is a bounded visual hypothesis for the navel region; no navel landmark exists in v0.1 rig calibration. The candidate does not claim an anatomical measurement or change the previous static renders.

Render it from the Windows checkout, using the existing clearance and en avant reports:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\guide_first_position_preview_v0_6.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --reference .\build\motion_studio\accepted_arm_reference_v0_6.json --source-profile .\build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json --clearance-report .\build\motion_studio\hand_clearance_candidate_v0_6\report.json --en-avant-report .\build\motion_studio\en_avant_outward_elbow_v0_6\report.json --output .\build\motion_studio\guide_first_position_v0_6
```

Evaluate `guide_first_front.png`, `guide_first_side.png`, and `report.json` as a static waypoint before rebuilding the motion path. The accepted second-position candidate remains intact; foot placement, navel landmark calibration, contact and choreography timing remain separate work.

The first midpoint render achieved a positive frontal hand gap (+0.02011681 armature units) and accurate rig endpoints, but its wrist height 1.18330568 remained closer to the calibrated chest bone head (1.23559117) than to the `spine_mid` bone head (1.10468304). The visual review found the hands slightly high for the guide's navel-level first position. A second static variant uses the calibrated `spine_mid` head **height only** as a bounded torso proxy, while preserving the midpoint front offset, wrist separation and geometric arm solve. `spine_mid` is not claimed to be the skin's navel landmark. Run the same script and inputs above with a separate output directory `build/motion_studio/guide_first_spine_mid_v0_6`; compare the two pairs of front/side PNGs before adopting either as a waypoint.

The spine-mid variant's actual front/side renders place the hands near the waist and forward of the torso; its measured frontal hand gap is +0.02838671 armature units with sub-tolerance arm and fingertip residuals. Use this as the **provisional guide first waypoint** in a new path diagnostic; it has not established movement quality. `guide_port_de_bras_path_preview_v0_6.py` checks the spine-mid static report and its source digests, reconstructs the exact waypoint from the same static inputs, and retains the previously reviewed Bra Bas and second endpoints. The old high en avant path and its failed overlap report remain diagnostic history.

On the Windows checkout, run:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\tools\blender\motion_studio\guide_port_de_bras_path_preview_v0_6.py -- --repo . --calibration .\build\motion_studio\low_poly_girl_calibration_v0_1.json --reference .\build\motion_studio\accepted_arm_reference_v0_6.json --source-profile .\build\phase10_6\low_poly_girl_canonical_pose_solver_v1.json --clearance-report .\build\motion_studio\hand_clearance_candidate_v0_6\report.json --en-avant-report .\build\motion_studio\en_avant_outward_elbow_v0_6\report.json --first-report .\build\motion_studio\guide_first_spine_mid_v0_6\report.json --second-report .\build\motion_studio\second_inward_line_v0_6\report.json --output .\build\motion_studio\guide_port_de_bras_path_probe_v0_6
```

Inspect `report.json` for the worst of all 49 evaluated frontal hand gaps and the 1/13/25/37/49 front and side views for silhouette defects. A positive measured frontal gap does not establish torso clearance or choreography approval; these samples do not encode authored movement tempo.
