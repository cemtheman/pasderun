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
