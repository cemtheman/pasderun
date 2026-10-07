# Pas de Run — Project Journal

## 2026-10-06 — Ballet Body Model v1 / Visual Validation Acceleration

### Baseline
- Repository: `cemtheman/pasderun`
- Main baseline: `080d42cb076a0efcc4902bbef7d9e42aae5550e3`
- Known safe product state: Phase 11.2.
- Motion Studio accepted upper-body reference: arm v0.6, with preparation -> opening -> second-position progression.
- Existing ballet-motion foundation already includes:
  - `canonical_ballet_skeleton_v1.json`
  - `anatomical_constraints_v1.json`
  - `ballet_pose_grammar_v1.json`
  - static rig/retarget contracts
  - foundation upper/lower motion contracts
  - a deterministic visual gate with 6 poses x 3 views.

### Decision
Do not rebuild ballet motion from scratch. Extend the existing canonical model into **Ballet Body Model v1** using a layered architecture:

```
Canonical Skeleton
  -> Anatomical / kinematic constraints
  -> Ballet technique constraints
  -> Balance / support / contact
  -> Style & phrasing
  -> Animation / gameplay
```

The objective is not muscle simulation. The objective is mechanically plausible, ballet-readable motion with repeatable visual verification.

### New model requirements
1. Preserve the current canonical skeleton and retarget pipeline where possible.
2. Separate:
   - structural/mechanical limit
   - functional ballet working range
   - current movement target.
3. Treat turnout as a distributed lower-limb chain, not foot yaw.
4. Add explicit support/contact and center-of-mass reasoning for plié, relevé, pointe and jumps.
5. Keep port de bras as a coordinated chain:
   thorax -> scapular/clavicular carriage -> shoulder -> elbow -> forearm -> wrist -> hand/fingers.
6. Add phase offsets so shoulder, elbow, wrist, fingers, head and gaze do not move robotically at the same instant.
7. Represent epaulement and gaze as coordinated pose intent rather than decorative head rotation.
8. Split foot behavior beyond one rigid foot segment where the current rig permits it; when the source rig cannot expose the ideal segmentation, preserve semantic sub-segments in the solver/contract and degrade gracefully at retarget.
9. Preserve bilateral asymmetry as a supported concept for support-leg / gesture-leg behavior.

### Visual validation policy
The existing Phase 10.6.8 visual gate is retained and expanded.

Machine geometry tests remain mandatory before visual review.

AI visual review is added as an **iterative engineering gate**, not as the final artistic acceptance authority.

Verdicts:
- `MACHINE_PASS / FAIL`
- `AI_VISUAL_PASS / REVISE`
- `HUMAN_ACCEPT / REVISE`

Work may iterate automatically while the first two gates are satisfied or improved. Final milestone acceptance remains human.

### Visual evidence pack
Every meaningful motion change must be capable of producing a deterministic review pack:
- fixed model, camera, orthographic scale and lighting;
- FRONT / THREE_QUARTER / SIDE views;
- identical framing between baseline and candidate;
- baseline and candidate contact sheets;
- overlay or difference view when useful;
- key pose stills;
- for motion: short deterministic preview and/or sampled frame strip;
- JSON metrics/report tied to the same commit.

### Review questions
Upper body:
- Are shoulders visually down and neck free?
- Do elbow, wrist and fingers form a continuous ballet line?
- Is the palm/forearm orientation plausible?
- Does second position look rounded rather than locked?
- Do head and epaulement support the phrase?

Lower body:
- Does turnout originate upstream rather than from foot yaw?
- Does knee track the second-toe direction?
- Does plié read as coordinated descent instead of squat/frog?
- Does relevé read over the forefoot with stable vertical organization?
- Is foot/ankle alignment plausible?
- Is pelvis/trunk compensation excessive?

Dynamic:
- Is weight transfer readable?
- Does COM remain plausible relative to support?
- Do take-off and landing use a coordinated absorption chain?
- Is motion phased rather than simultaneous/robotic?

### Method
For each roadmap step:
1. Read the journal and roadmap.
2. Verify branch and baseline.
3. Run existing tests before editing.
4. Make the smallest coherent change.
5. Add/adjust automated tests.
6. Generate deterministic visual evidence.
7. Inspect the evidence visually.
8. If `AI_VISUAL_REVISE`, identify the exact visible defect and iterate.
9. Re-run focused tests, then full relevant suite.
10. Record evidence paths, metrics, screenshots and decision in the journal.
11. Do not silently weaken constraints or tests to obtain PASS.
12. Stop only at explicit human-review checkpoints or a genuine blocker.

### Immediate next milestone
**BBM-1: Upper-body proof on accepted Motion Studio arm v0.6**

Goal: reproduce or improve the accepted preparation -> opening -> second-position phrase using the extended model while proving that the new architecture does not regress the accepted visual quality.

Success requires:
- no regression in existing automated ballet-motion tests;
- deterministic baseline-vs-candidate render pack;
- visually improved or equal shoulder/elbow/wrist/hand continuity;
- phase-offset support;
- no source GLB mutation;
- no unrelated gameplay change.

### Status
Roadmap created. Work handoff prompt prepared. No production/gameplay source change has been made by this documentation update.

## 2026-10-06 — Overnight run / BBM-0 audit in progress

- User override: advance beyond BBM-1 without routine human approval when machine, test and AI visual gates pass; preserve final human artistic review. This supersedes the older BBM-1 stop instruction in the roadmap/prompt.
- Initial clone: `main`, HEAD `080d42cb076a0efcc4902bbef7d9e42aae5550e3`, working tree clean.
- Required methodology documents exist on `origin/docs/ballet-body-model-v1-roadmap`, not main. All three were read in full.
- Work branch: `work/bbm-v1-overnight-20261006`; starting SHA `9a544d5897a3609d2838e30f9ae7d00f44aefc43`. Safe main is an ancestor; only the three methodology documents differ.
- Accepted Motion Studio reference locked separately at `27c61f3c34ebade7ae7027655f9e546eea4916c1` in a detached reference worktree; no merge or reference modification.
- Baseline tests: `python3 -m unittest discover -s tools/ballet_motion -p 'test_*.py'`: 198/198 PASS. `python3 -m unittest discover -s tools/blender -p 'test_*.py'`: 106/106 PASS. These are Python tests, not Blender geometric/render evidence.
- Environment: Python 3.12.14; Blender executable and bpy absent. Generated Phase 10 profiles/renders are absent from clone (ignored outputs).
- Recovery: bpy package lookup failed on configured and explicit PyPI index. Initial apt failed because container cannot switch uid/groups; running apt with its documented sandbox user set to root successfully fetched package indices. Blender installation is in progress. No approval escalation, source GLB mutation, invariant change or product edit.
- Geometric gate: NOT RUN. Visual evidence: NOT YET GENERATED. AI verdict: NOT REVIEWED (no PASS inferred from tests).
- Next action: finish render-tool recovery, regenerate calibration through retarget profiles and the existing 18-cell foundation gate. Only advance after actual visual inspection.

### BBM-0 — baseline evidence lock

- Starting SHA: `9a544d5897a3609d2838e30f9ae7d00f44aefc43`; branch `work/bbm-v1-overnight-20261006`. Ending SHA: resolve with `git log -1 --format=%H -- tools/visual_validation/run_bbm0_baseline.py` (avoids self-referential commit hashes).
- Changed files: this journal; `tools/visual_validation/run_bbm0_baseline.py`; baseline evidence pack under `build/visual_validation/BBM-0/baseline/`.
- Tool recovery succeeded: downloaded Ubuntu Blender 4.0.2 packages into scratch, extracted without system installation; explicit scripts/data/library paths, system Python extensions and existing NumPy allow GLB import and workbench rendering. Blender 5.2 is not available; the actual version is recorded rather than assumed.
- Added cross-platform runner delegates unchanged Phase 10.6.1 through 10.6.8 authorities. No constraint/test weakening.
- Calibration, canonical profile, constraint profile, grammar, solver, retarget: PASS. Existing renderer produced 18/18 cells; static realization, mesh contact, axial wrist continuity, hand mesh spacing, seed preservation, bounded clearance and hand shaping all PASS.
- Source GLB SHA256 before/after: `a162d8730238a76ba1d6b31910c98fb1f5640c46917983e0bbad04095e81b7b2` unchanged.
- Evidence: `build/visual_validation/BBM-0/baseline/contact.png`, `geometry_report.json`, `manifest.json`, `review.md`, per-view cells and runner logs.
- Actual visual inspection: all 18 cells viewed in contact sheet. `AI_VISUAL_PASS` for baseline reproducibility/evidence lock only. Inherited artistic defects remain recorded in review.md; this is not approval of those poses.
- Risk: latest Motion Studio branch uses a different GLB SHA256 `3627f15a7d5e94b8821767a3617af6830642c38a229a7577fbf654473c63a446`; do not copy that mesh into the safe product branch. Need distinguish historical accepted arm phrase from later experimental first-position/finger repairs.
- Next: inspect historical accepted phrase checkpoint and exact compatible inputs before BBM-1; preserve the locked source mesh.

### BBM-1 — accepted reference recovery

- BBM-0 ending SHA: `f5558faaa6c89e420728270f16da7dbd0205336d`.
- Historical accepted arm path located at `978df231acd79394556ff21828ff2da405d4674b`; screened implementation `c8c669519790a3af7c9425ce9eb2021ccdd8e6ee`. Its source GLB matches safe main exactly. Later first-position experiments and ring repair assets are excluded.
- Restored only the existing arm solver's Python dependency closure, associated schemas/fixtures/tests and two existing Blender adapters, byte-for-byte from that checkpoint. No production stack rewrite or mesh edit.
- Calibration bridge and accepted reference extraction PASS against newly regenerated safe-main profiles. Initial restored tests exposed missing test-only imports/fixtures; dependency closure corrected; 38/38 PASS.
- Next: reproduce the accepted 49-sample phrase with fixed three-view camera, measure all samples, then extend phase/carriage/head coordination incrementally. BBM-1 is not yet passed.

### BBM-1 — retarget and visual revisions (still in progress)

- Historical replay: 45/49 samples fail existing axial wrist reconstruction gate (e.g. frame 1 error 0.07170022 > 0.01). Joint endpoint tests alone were insufficient. Report: `build/visual_validation/BBM-1/accepted-replay/report.json`.
- Wrist-only analytic projection: wrist gate corrected, but 25 endpoint/mesh-gap failures remain. This experiment is rejected; no thresholds changed. Report: `BBM-1/wrist-two-dof/report.json`.
- Forearm/wrist coupled fitting inside the existing preferred pronation and wrist envelopes: 49/49 sampled geometric gates PASS. Visual review REVISE: excess finger splay and downward hand break at opening. Existing finger-only shaping applied; source GLB unchanged.
- Phrase layer added bounded separate elbow, hand and head phases; small measured clavicle carriage; 0.25-degree chest epaulement and 4-degree head turn are style hypotheses, not anatomical measurement. Scapula has no separate rig bone and is represented semantically; gaze follows head because no calibrated independent eye control is established.
- Added all-sample joint orientation continuity gate (30-degree maximum adjacent review-grid step) and unchanged root/foot/toe anchor gate. First phrase run exposes 49.8/62.4-degree forearm/hand jumps at frames 33/34. Cause: reference-axis switching. No gate relaxed.
- Parallel-transport reference: 49/49 gates PASS; max step 19.18 degrees. Actual 3-view strip review REVISE: end palms turn too far toward audience.
- Elbow-plane reference: 49/49 gates PASS; max step 19.41 degrees. Static endpoint appearance improves, but actual 12-frame opening montage at frames 29–40 shows unwanted intermediate palm rotation. AI_VISUAL_REVISE remains. Five evenly spaced frames alone had hidden this defect.
- Historical renders are explicitly marked `MACHINE_FAIL` / diagnostic-only; never advance on them. These show the previous phrase for comparison, not approved new evidence.
- Blender contact-sheet save produced one truncated PNG despite process success. All 15 underlying cells decode fully. Pillow reassembly (no pixel retouching) produces `verified_frame_strip.png`; raw truncated file is not review evidence. Future evidence generation must fully decode files before acceptance.
- Added phase tests: monotonic/end-exact bounded offsets, invalid inputs rejected, non-simultaneous chain phases; restored arm solver suite plus new tests: 41 PASS.
- Next iteration changes only intermediate hand-line intent toward forearm continuity, retaining exact phrase waypoints and bone lengths. BBM-1 remains incomplete; BBM-2 has NOT started.
- Git transport dry-run failed: terminal has no GitHub HTTPS username credential. GitHub connector remains accessible; use immutable blob/tree/commit API mirror if needed. No main/production/deploy mutation.

### BBM-1 — isolated diagnostic checkpoint / autonomous stop condition 5

- Starting SHA `f5558faaa6c89e420728270f16da7dbd0205336d`; ending source SHA: `git log -1 --format=%H -- tools/motion_studio/bbm_upper_body_v1.py`. Branch `work/bbm-v1-overnight-20261006`.
- Files: restored arm solver dependency closure and regression fixtures, `bbm_upper_body_v1.py` + phase tests, two historical Blender adapters, `render_bbm1_upper_body_v1.py`, BBM-1 replay runner/provenance, journal, reviewed evidence/report pack. No production source or GLB changes.
- Latest candidate rerun from final source: 49/49 implemented geometric samples PASS; max adjacent rotation 19.40584 degrees; anchors unchanged. Latest hand-line experiment: 49/49 PASS; max step 19.96427 degrees.
- Final tests: ballet-motion 198 PASS; Blender contract/runner tests 106 PASS; Motion Studio 41 PASS; total 345 PASS. Syntax checks and `git diff --check` PASS. Full Godot gameplay/export build not run because gameplay and production files are untouched.
- Actually reviewed final three-view strips and full opening 29–40 montages. Both candidates AI_VISUAL_REVISE. Elbow-plane fit keeps wrong intermediate palm rotation; hand-line fit trades this for visibly upward-facing offering/scoop palms. Last two correction attempts do not produce an acceptable whole phrase. User stop condition 5 applies.
- Successful active milestone remains BBM-0. BBM-1 is a committed isolated diagnostic experiment, NOT an accepted model or gameplay asset. BBM-2..8 NOT STARTED.
- Key evidence: `build/visual_validation/BBM-1/historical-diagnostic/verified_frame_strip.png`; `candidate/verified_frame_strip.png`, `candidate/opening_continuity_29_40.png`, `candidate/motion_preview.gif`; equivalent files under `opening-hand-line/`; `review.md`, reports and hash manifest.
- Raw duplicate intermediate images were archived in scratch `bbm1_intermediate_raw`; all intermediate reports and reviewed strips remain in the repo. Primary final/historical raw cells and full 49-frame previews are retained. Truncated Blender-assembled strip is excluded; decoded Pillow strips are authoritative.
- Unresolved risk: true elbow hinge/forearm axial calibration and palm-plane intent need a coherent coupled solution. A per-frame nearest-orientation search is not yet a reusable accepted body model. Scapular semantics are approximate on this rig; hair/costume limit anatomy review. No source repair required by current evidence.
- Next action: explicit palm-normal intent through accepted anchors and opening; coupled upper-arm/forearm/wrist solve; unchanged anatomical, length/contact and wrist gates; 29–40-frame visual review before considering BBM-1 promotion.

### Durable checkpoint publication and morning handoff

- BBM-0 local `f5558faaa6c89e420728270f16da7dbd0205336d` → published `5c9751685660348f6509f2d104d4251ce3391e38`; identical Git tree `fcee0ffdaec845bab81962b0aa12bec81a8479ae`.
- BBM-1 local `38dd7a3c116ffbd8d34bb90d562d1bab1561d9fd` → published `7ae123916f64486337ff6b3324f50cd8f9f0de21`; identical Git tree `82e254463d53b9a74e9809bc387664f8247a95d0`. Commit IDs differ because GitHub connector creates commit metadata; all blob/tree hashes match exactly.
- Branch: `work/bbm-v1-overnight-20261006`. No main mutation, merge, deploy or GLB change.
- Large 222-path GitHub tree request timed out once; diagnosed API size/time constraint and recovered via 28-entry incremental trees. Final tree equals the exact local checkpoint. No repeated failed large request.
- Every one of 173 retained PNGs fully decoded. Candidate report source hashes bind to the committed renderer/model, supplementing the starting Git SHA recorded during development.
- Morning Handoff: `docs/MORNING_HANDOFF_BBM_V1_2026-10-07.md`, includes exact source/published checkpoint mapping, tests, gate scopes, reviewed visual paths, stop condition 5 and the next palm-plane coupling step.
- Final metadata/documentation checkpoint does not promote BBM-1. Last accepted active milestone remains BBM-0; BBM-1 REVISE, BBM-2..8 NOT_STARTED.

### BBM-1 continuation explicitly reopened by user

- User instruction: “bence devam edilebilir durumda”; previous stop decision reopened. Starting SHA `a3277e857b937ca48561599bc73a188e1f92b1a2`, clean branch `work/bbm-v1-overnight-20261006`.
- Next isolated experiment: explicit palm-plane normals interpolated from source-bound historical anchors, projected onto the current hand direction; coupled feasible forearm/wrist fitting remains inside unchanged preferred anatomical envelopes and endpoint/contact gates. No GLB or production changes.
- Evidence destination: `build/visual_validation/BBM-1/palm-intent/`. Visual verdict pending actual rendering/review; BBM-1 remains REVISE.

- Palm-intent iteration: 49/49 implemented geometric gates PASS; 345 regression tests PASS. Actual three-view strip and opening montage inspected: AI_VISUAL_REVISE, retarget/ballet-technique class; downward wrist break remains at mid-opening. Smallest next layer is opening-only hand-line intent combined with the palm-plane objective; no anchor or gate changes.

- Combined palm/hand-line and early palm lead: both 49/49 geometry PASS; actual opening montages remain REVISE (upward offering palms). Earlier palm rotation changes first opening frames but not the problematic feasible branch. Diagnose forearm gauge: elbow-plane reference is not the source-bound canonical rest transport. Next experiment uses the existing canonical-basis conversion of the historical posed forearm; no pronation/wrist envelope widening.

- Source-bound rig-rest gauge run: 49/49 gates PASS, actual 3-view and 29–40 review REVISE; offered palms persist. This falsifies a gauge-only correction. Next layer: whole-phrase discrete roll path planning across feasible forearm/wrist candidates, squared palm-normal error plus rotation smoothness, each adjacent hand rotation <=20 degrees (existing fitter bound). No envelope or machine gate relaxed. Full second pass rerenders and checks the selected path independently.

- Global discrete roll path: 49/49 gate PASS, reviewed three-view strip + opening montage REVISE; unchanged visible offered palms. Greedy-path diagnosis alone is insufficient. Next smallest layer is intermediate wrist intent: smoothly blend toward the existing neutral wrist relationship only inside opening (sin² window, exact anchor hand targets retained), preserve hand bone length, fit forearm roll to palm intent, and independently recheck original wrist/contact/endpoint gates.

- Neutral wrist + global path: 49/49 gates PASS, 3-view strip, 29–40 montage and enlarged hand detail inspected. Still REVISE. Palm-normal audit shows only 3.1–3.6° target error at frames33/37; palm roll is already following intent. Revised diagnosis: opening wrists rise while endpoint-linear elbow poles stay too low, producing the offering silhouette. Correct smallest elbow coordination layer: lag the historical sampled bend-pole path rather than interpolate only endpoint poles, preserving its opening arc. All anchor targets remain exact.

### BBM-1 continuation accepted engineering checkpoint

- Starting SHA `a3277e857b937ca48561599bc73a188e1f92b1a2`; ending SHA resolves with `git log -1 --format=%H -- tools/motion_studio/palm_roll_path_v1.py`; branch `work/bbm-v1-overnight-20261006`.
- Changed: isolated upper-body phase model and renderer, evidence runner, reusable palm roll path planner + four meaningful tests, retained continuation reports/strips and final complete evidence pack. No production/gameplay/GLB edits.
- Tests: Motion Studio45, ballet-motion198, Blender106: 349 PASS. Geometric final49/49 PASS, unchanged wrist reconstruction/endpoint/mesh gap/length/contact envelopes; source hash unchanged.
- Final evidence: `BBM-1/elbow-path/verified_frame_strip.png`, `opening_continuity_29_40.png`, `preparation_01_24.png`, `opening_25_49.png`, complete49-frame preview + GIF, report/source hashes, review. Actually inspected all49 front frames and three-view keyframes. AI_VISUAL_PASS against accepted v0.6; previous candidates remain REVISE.
- Root cause correction: historical sampled elbow bend-pole arc retained under phase lag, coordinated neutral intermediate wrist intent, explicit palm normals and globally continuous feasible roll path. No source repair or gate widening.
- Duplicate intermediate raw cells/previews moved to reproducible scratch archive; all reviewed intermediate strips/reports retained, final raw cells and full preview retained in repo. `continuation_manifest.json` binds retained files.
- Unresolved risks: costume/hair occlusion, semantic-only scapula, gaze=head, review-grid timing; human artistic review remains morning task. Next action BBM-2 distributed turnout/alignment audit and fixtures; BBM-8 production integration remains gated.

### BBM-2 initial alignment/stance audit

- Starting/published BBM-1 SHA `931ef8bd9e3353e0e65c4cd087cdc6e56b051796`, identical tree to local `daa264e3f0110441adfccc77507faf680a098e47`; clean tracking work branch restored. BBM-1 PASS checkpoint published without main mutation.
- BBM-2 isolated distributed turnout helper + four tests: hip request authoritative, knee contribution derived within existing flexion cap, independent foot yaw always zero; observed knee anterior/toe-ray proxy instead of authored zero tracking error; arch observation explicitly unavailable on rig.
- Initial three-view first/fifth/plie baseline/candidate pack: 0 measured tracking failures (<=2.63°, existing preferred6°/hard12° unchanged), contact/wrist gates PASS. Actual images REVISE: first hip adduction=-6° crosses the legs/heels. Minimum correction layer: source-mesh heel inner-gap bounded hip adduction solve; no ankle yaw, GLB change or envelope widening. Evidence retained `BBM-2/iteration-01/`.
- Current BBM-2 tests202 + Motion45 + Blender106 =353 PASS. BBM-2 remains in progress; BBM-3 not started.
- One BBM-2 rerun failed before rendering due an edit joining two Python statements. Fixed that line and added pre-run compilation; no geometry/tool retry of unchanged failure.

- Second first-stance iteration: bounded mesh-aware hip adduction resolves first heel gap to +0.000982 (target0.000976 armature units), no independent foot yaw. First front/3Q images inspected: closer plausible first stance. Overall BBM-2 still REVISE: inherited fifth is a spaced V, and inherited plié rear heel centers cross (mesh projected inner gap -0.048). Next smallest lower stance layer: close plié with same bounded contact-aware adduction solve; fifth uses hip-origin 60° turnout and symmetric +/-6° hip flexion/extension with straight knees to place one foot ahead, no foot-yaw authority. All existing contact/envelope/alignment gates retained.

### BBM-2 accepted engineering checkpoint

- Starting SHA `931ef8bd9e3353e0e65c4cd087cdc6e56b051796`; ending SHA resolves via `git log -1 --format=%H -- tools/ballet_motion/distributed_turnout_v1.py`; branch `work/bbm-v1-overnight-20261006`.
- Changed files: isolated `distributed_turnout_v1.py`, four tests, BBM-2 Blender renderer/evidence runner, retained iteration01/02 plus final fixed 18-cell paired pack/report/hash manifest, journal. Source/main/gameplay unchanged.
- 353 tests PASS (202+45+106); all final contact/preferred/retarget/wrist/tracking gates PASS. Max observed tracking4.94° < unchanged6° preferred; independent foot yaw0. First/plie heel gap~0.00098 after bounded source-mesh hip adduction search.
- Actually inspected final baseline/candidate FRONT/3Q/SIDE sheets: AI_VISUAL_PASS. First closure, conservative closed fifth with upstream60° hip and opposing +/-6° hip flexion/extension, plié heel correction; no contact/envelope relaxation.
- Artifacts: `BBM-2/baseline/contact.png`, `candidate/contact.png`, all18raw cells, `report.json`, `review.md`, `manifest.json`. Earlier REVISE packs retained.
- Risks: single-toe tracking proxy, unobservable arch/pronation, partial turnout fifth; no production integration. Next BBM-3 semantics + visual proofs.

### BBM-3 foot semantics / evidence run in progress

- BBM-2 local4f586cea9f386846b6a8a631feba2f0b33fa1462 → published3938f89aff2cab5504a7d070f3f420d04c8fb035, identical tree; tracking work branch restored, no main mutation.
- Starting BBM-3 commit3938f89. Isolated foot semantic states + four tests distinguish FULL_FOOT, FOREFOOT and TOE_REGION_PROXY support; arch/hindfoot without separate bones stay semantic; no full-en-pointe claim. Ankle preferred50°/hard60° unchanged; pointe-ready cannot expand these.
- Render fixture uses accepted first-position turnout/closure and BBM-1 carriage, existing ankle/toe retarget and deformed-mesh contact solver. Candidate adds bounded hip flexion adjustment to bring pelvis projection toward observed low forefoot support centroid (limited proxy, whole-body COM remains BBM-4). Fixed18-cell paired pack in BBM-3.
- Tests206 ballet-motion +45Motion+106Blender =357 PASS for current pure helpers; actual BBM-3 geometry/visual verdict pending complete render. One diagnostic read used a wrong toe joint class key; corrected to existing mtp_hinge, no code/constraint change.

- BBM-3 iteration01: machine PASS, actual18-cell and enlarged foot-detail review REVISE (retarget): flat/demi/pointe-ready insufficiently distinct. Pelvis support proxy improves to<0.0003; geometric PASS is not visual PASS.
- Diagnosis: canonical foot BODY_FRONT neutral differs from physical source-mesh flat-contact neutral. Locked BBM-0 realization requires32.377°left/32.392°right canonical plantar. Isolated next candidate introduces explicit source-bound neutral calibration; anatomical requested0..50° remains inside original preferred envelope, encoded canonical angle includes measured neutral offset. No anatomical limit file changed; boundary tests verify51°SOFT and61°HARD still reject. Post-application matrix roundtrip, decoded anatomical angle and unchanged deformed forefoot contact enforced. Legacy production/static path unchanged.
- A patch command had an unterminated replacement string; no edit executed. Its unintended old-script render was interrupted, then the patch rebuilt using multiline literals and compilation before any new run.

- Calibrated foot iteration02 renders all18 cells and enlarged details: visibly distinguishes demi and elongated pointe-ready. Contact and decoded anatomical envelopes/matrix proof PASS, but pointe-ready planar toe-ray tracking fails36.1° under inherited closed-first hip adduction; no gate loosened. AI_VISUAL_REVISE. Minimal next stance correction: pointe-ready uses an open symmetric preparation (hip adduction0, same upstream45° turnout), while flat/demi retain accepted closed first. This removes the closed-stance toe projection conflict without free foot yaw or changing12°hard/6°preferred tracking.
- Corrected one input-loader call accidentally affected by a metadata string replacement, before successful iteration02 rendering.

- Open pointe-ready stance passes observed tracking (0.064°), anatomical/contact gates and visually separates pointed foot preparation from flat/demi. Before promotion, added independent toe matrix/DOF proof; this exposed1.06096e-5 reconstruction error vs unchanged1e-5 threshold in inherited transpose-based application. No threshold changed. Diagnosis: imported affine rest-frame skew accumulates into child toe frame. Isolated foot/toe application now solves rest/parent relations with exact matrix inverses and a proper rotation target; joint translations preserved. Final rerender pending; BBM-3 still unaccepted.

- Added unchanged local rotation orthogonality/determinant and bone-length checks before BBM-3 promotion. This catches Foot_R local orthogonality2.086e-5 >1e-5, while world reconstruction previously passed. No threshold widened. Imported/serialized parent matrix rounding accumulates small affine error; isolate correction by projecting local rotation payloads onto SO(3) before calibrated foot/toe application. Contact/angle/matrix/length gates remain exact. Failed-run output now deletes stale prior reports/cells and writes fatal MACHINE_FAIL report, preventing mixed or stale evidence.

- Rotation diagnostic (scratch bbm3_rotation_diagnostic.log): source Foot_R rest orthogonality9.54e-6, accumulated parent23.0e-6. Proper local rotation projection realizes world column error3.25e-6, orientation error2.06e-6 and shaft length relative error7.82e-7, all below existing1e-5 bounds. Select this representation: exact inverse relation followed by SO(3) local rotation projection, independently enforce realized matrix/DOF and unchanged length/contact gates. Diagnostic run explicitly nonpromotable; no source or threshold change.

### BBM-3 accepted engineering checkpoint

- Starting SHA3938f89aff2cab5504a7d070f3f420d04c8fb035; ending source SHA resolves via `git log -1 --format=%H -- tools/ballet_motion/foot_semantics_v1.py`; branch work/bbm-v1-overnight-20261006.
- Changed: isolated foot semantics + five meaningful tests, Blender foot proof, decoded evidence runner, iteration reports/strips plus final18raw cells, enlarged details, report/hash manifest/review; journal. Source GLB/production/main unchanged.
- 358 tests PASS (207+106+45). All final source-bound anatomical/local/world rotation, length, toe-ray tracking, contact and wrist gates PASS. Max candidate tracking1.80°; demi heel~0.078, pointe-ready~0.136 armature units. No thresholds or hard limits widened.
- Actually inspected final paired3views and enlarged foot sheets: AI_VISUAL_PASS for conservative flat/demi/pointe-ready preparation. Pointe-ready accepted in open symmetric support; full en-pointe not claimed. Earlier failed closed stance and incomplete matrix proofs remain REVISE diagnostics.
- Key artifacts: BBM-3/baseline/contact.png +foot_detail.png, candidate/contact.png +foot_detail.png, report.json,review.md,manifest.json. Intermediate duplicate raw cells archived reproducibly in scratch; reviewed strips/reports retained.
- Reference correction is explicit: raw canonical ankle angle includes source-neutral32.377°L/32.392°R; anatomical angle remains relative neutral and capped by existing preferred50°/hard60°. Numerical local SO(3) projection resolves imported parent error while preserving independent1e-5 world/length gates.
- Risks: source footwear silhouette, semantic-only arch/hindfoot, no full en-pointe, pelvis proxy not whole-body mass COM. Next BBM-4 measured support polygon + declared COM proxy, asymmetry and one-leg support fixtures.
- Final supplementary foot-detail crop uses uniform2× enlargement (160×140→320×280); corrected earlier nonuniform square enlargement. Primary420×420 raw cells/3-view sheets and all pose geometry unchanged; use primary evidence or final aspect-preserving detail for review.

### BBM-3 accepted locally; execution environment interrupted before publication

- Starting SHA3938f89aff2cab5504a7d070f3f420d04c8fb035; branch work/bbm-v1-overnight-20261006. Ending local HEAD bbddfeb6ab392c113dd8a26acc94ff3fceb4ad1f; exact tree3c020c327ff6fb9bd607f96ff60fff6fc2fb501d. Last terminal git status clean.
- Changed: foot_semantics_v1.py +5 tests, render_bbm3_foot_v1.py, run_bbm3_evidence.py, retained paired18-cell evidence/reports/iterations, journal/handoff. Source GLB unchanged; no production edits or constraint relaxation.
- 358 tests PASS (207+106+45), syntax/diff PASS. Existing anatomical/contact/tracking/wrist/length/reconstruction thresholds preserved. Source-bound flat ankle neutral32.377/32.392° used to interpret anatomical plantar; preferred50/hard60 unchanged. Imported affine rest skew solved with actual inverses and normalized local rotations; independent world/length proofs PASS.
- Actually inspected paired three-view flat/demi/pointe-ready sheets and enlarged details: AI_VISUAL_PASS for conservative preparation only, not full en-pointe. Demi heel~.078m; pointe-ready~.136m. Pointe-ready open stance corrects near-vertical toe-ray tracking without waiving6/12° limits. Arch remains semantic, pelvis proxy is not whole-body COM. Details in local BBM-3 review/report; full intermediate journal is present in local commit but not yet published.
- Visual paths build/visual_validation/BBM-3/{baseline,candidate}/contact.png and foot_detail.png;18raw cells, report/review/manifest. Final supplementary crop corrected to uniform2×; source renders unchanged. Final crop reopening could not finish after environment failure.
- Publication failed strict Git blob SHA check for baseline/01_flat_three_quarter.png (expected acb52c2e9fc23b9cdcf7cfb5036896fa0544fe58; isolated API attempt returned9a5f157f0c2f602bddf853fd5ef315d8aedd6920). No mismatched tree/ref was published. Subsequent command failed exec-server transport/recovery timeout; separate minimal command, non-login command, and view_image recovery attempts did not respond. No repeated unverified branch update.
- Remote last verified code/evidence checkpoint remains BBM-2 at3938f89aff2cab5504a7d070f3f420d04c8fb035. This documentation is saved directly through connector while terminal unavailable, and cannot imply local/remote code parity.
- BBM-4 not implemented. Next: restore execution, verify/publish exact local BBM-3 tree and preserve local full journal, then implement observed support polygon/COM proxy/balance margin/support roles. Morning handoff rewritten to disambiguate current PASS from historical REVISE. No human preference question pending.

### 2026-10-07 — environment recovered and continuation

- Execution and Blender files survived maintenance. Starting local SHA bbddfeb6ab392c113dd8a26acc94ff3fceb4ad1f, clean tree verified before edits; remote docs-only9ba5f31 reconciled while preserving complete local BBM-3 chronology. No BBM-4 changes yet. Reverify evidence and publish, then BBM-4.

### 2026-10-07 — BBM-3 publication recovered; BBM-4 starts

- Published recovered local ab70a7a as9516b79a76b9a687dc32b4225df8c85a109cb3d7, identical tree d0f244255d5c577000cf5ebc1f977bc0a6d73ee8. All52changed blobs SHA-verified. Smaller50000-character base64 reads recover transfer; previous mismatched blob never referenced. BBM-3 source bindings and all retained PNG decode PASS; actual final aspect-preserving foot detail inspected PASS. Tracking work branch restored.
- BBM-4 starting9516b79. Proposed practical balance diagnostic: observed deformed contact polygon, area-weighted surface centroid proxy (not tissue-mass COM), signed margin, declared SUPPORT/SWING roles, unchanged contact/ankle/toe/length/wrist/tracking checks. No source mesh change; flat/demi/one-leg and transitional static fixtures first. Visual verdict pending.

- BBM-4 iteration01: baseline/candidate 24cells inspected. Candidate balance margins positive (~.01–.06), but transitional SWING foot penetrates~.05; MACHINE_FAIL/AI_VISUAL_REVISE anatomy/contact. Smallest correction only gesture leg18°hip/55°knee instead12°/30°. Support sampling now explicitly uses unchanged contact low quantile0.1 rather20% (more conservative proxy); contact tolerance unchanged. Initial evidence retained iteration-01.

### BBM-4 accepted engineering checkpoint

- Starting9516b79; ending source SHA resolves via git log -- tools/ballet_motion/support_balance_v1.py. Branch work/bbm-v1-overnight-20261006. Changed new support helper+4tests, isolated renderer/runner, paired24raw cells +support_proxy +report/review/manifest, retained failed iteration, journal.
- 362 tests PASS (211/106/45), all final geometric gates PASS. Observed root lateral <=1.9e-9; support margins .00997..05962 positive. One-leg clearance .1505; transitional .0396. Source/machine hashes verified. Contact/wrist/foot/6°tracking/1e-5 local/world/length tolerances unchanged.
- Actually inspected all24 paired cells and final candidate/support chart: AI_VISUAL_PASS. Geometry-based surface-density COM proxy explicitly limited by costume/hair; static practical support only, no dynamic/clinical claim. Previous swing penetration REVISE corrected only gesture leg. No GLB/gameplay changes.
- Paths BBM-4/baseline/contact.png, candidate/contact.png, support_proxy.png, report/review/manifest. Unresolved: geometric proxy versus actual tissue COM; next BBM-5 deterministic plié/weight-transfer chain.
