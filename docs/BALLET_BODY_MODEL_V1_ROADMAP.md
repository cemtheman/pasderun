# Ballet Body Model v1 — Roadmap and Methodology

## Purpose
Evolve the existing Pas de Run ballet-motion stack into a literature-informed, visually verifiable body model without discarding the current canonical skeleton, retarget pipeline, pose grammar or accepted motion work.

## Non-goals for v1
- full muscle-force simulation;
- medical diagnosis or dancer-specific clinical range prediction;
- replacing the source character mesh;
- changing gameplay unrelated to movement quality;
- granting an automated system final artistic approval.

## Architecture target
```
Canonical rig semantics
  -> anatomical envelopes
  -> coupling constraints
  -> ballet technique grammar
  -> support/contact/balance
  -> movement phrase timing
  -> retarget
  -> deterministic visual evidence
  -> AI engineering review
  -> human milestone acceptance
```

## Milestones

### BBM-0 — Baseline audit and evidence lock
Deliverables:
- confirm `main` baseline SHA;
- inventory current ballet-motion contracts, tests and generated assets;
- run current focused ballet-motion tests;
- regenerate the existing Phase 10.6.8 contact sheet if the environment supports Blender;
- archive baseline render/report references for comparison.

Gate: no edits until baseline is reproducible or the exact environmental blocker is recorded.

### BBM-1 — Upper-body proof: accepted arm v0.6
Add or formalize:
- scapular/clavicular participation;
- shoulder/elbow/forearm/wrist chain coordination;
- joint phase offsets;
- hand/finger line intent;
- epaulement/head/gaze coordination.

Use the accepted preparation -> opening -> second phrase as the regression target.

Visual gate:
- fixed FRONT / 3Q / SIDE keyframes;
- baseline vs candidate;
- shoulder elevation;
- elbow roundness;
- wrist discontinuity;
- palm flip;
- hand centerline and silhouette;
- phrase timing.

Exit: candidate is visually equal or better and all relevant tests pass.

### BBM-2 — Turnout and alignment model
Replace any implicit `turnout == foot yaw` assumptions with a distributed chain model.

Required semantics:
- hip external rotation as primary authority;
- knee axial contribution derived and flexion-dependent;
- foot progression is observed output, not free turnout authority;
- pronation/arch collapse is not turnout;
- knee-second-toe tracking;
- compensation metrics.

Exit: first/fifth/plié visual fixtures remain plausible across 3 views with compensation warnings measurable.

### BBM-3 — Foot, demi-pointe, relevé, pointe semantics
Model:
- ankle plantar/dorsiflexion;
- hindfoot alignment;
- midfoot/arch semantic state;
- MTP/toe articulation;
- support-area changes from flat -> demi-pointe -> pointe.

If the production rig lacks separate bones, keep semantic solver fields and retarget them conservatively.

Exit: relevé and pointe-ready poses read correctly without foot yaw cheating, ankle collapse or implausible COM placement.

### BBM-4 — Balance/support solver
Add:
- support foot/feet;
- support polygon or practical proxy;
- projected COM;
- balance margin;
- support-role asymmetry;
- contact invariants.

Exit: flat, demi-pointe, one-leg support and selected transitional poses produce stable support diagnostics and no visible root drift.

### BBM-5 — Plié and weight-transfer chain
Coordinate:
- pelvis;
- hip flexion;
- maintained turnout;
- knee flexion;
- ankle dorsiflexion;
- heel/contact policy;
- trunk organization.

Exit: plié reads as ballet descent, not squat; transitions into and out of plié preserve alignment.

### BBM-6 — Jump take-off / flight / landing
Four states:
- PREPARATION
- TAKEOFF
- FLIGHT
- LANDING

Add visual and metric checks for:
- push sequence;
- toe/ankle/knee/hip extension;
- airborne organization;
- landing absorption chain;
- no straight-knee impact look.

Exit: deterministic preview passes machine checks and AI visual review.

### BBM-7 — Phrase composition and style
Add phrase-level timing:
- joint phase offsets;
- easing profiles;
- breath/softness controls;
- head/gaze lag;
- style modifiers that do not violate anatomical or technique constraints.

Exit: multiple phrases can share the same physical foundation without bespoke per-motion hacks.

### BBM-8 — Pas de Run gameplay integration
Integrate only after model gates pass.

Rules:
- motion system remains single-authority;
- no regression of Phase 11 gameplay topology/timing;
- gameplay change and body-model change must be separable in commits;
- preserve rollback path to safe SHA.

## Deterministic visual-validation harness

### Static pack
For each selected pose:
- FRONT
- THREE_QUARTER
- SIDE

All candidates use identical:
- character;
- camera;
- scale;
- lighting;
- ground;
- framing.

### Dynamic pack
For each phrase:
- start / 25% / 50% / 75% / end frame strip;
- optional short low-bitrate MP4 or GIF;
- key transition frames chosen deterministically from time, not manually.

### Comparison artifacts
Recommended output:
```
build/visual_validation/<milestone>/
  baseline/
  candidate/
  comparisons/
  report.json
  review.md
```

`report.json` records:
- git SHA;
- contract/input SHA256 values;
- test status;
- geometric metrics;
- render settings;
- sampled frame times.

`review.md` records:
- visible defects;
- AI verdict;
- exact correction attempted;
- human decision when applicable.

## AI visual-review protocol
The reviewer must judge visible evidence, not code intent.

For every candidate answer:
1. What improved?
2. What regressed?
3. Is the defect anatomical, ballet-technique, retarget, timing, camera, or mesh-related?
4. Which parameter/code region is the smallest likely fix?
5. Is another render required?

The reviewer must not issue a PASS when:
- framing differs from baseline;
- evidence is missing;
- automated geometric gate failed;
- only one flattering view is shown;
- the change fixes one view by breaking another.

AI verdicts are provisional engineering decisions. Final milestone acceptance belongs to the user.

## Stop conditions for autonomous Work
Stop and ask for human review when:
- BBM-1 candidate is AI_VISUAL_PASS and regression tests pass;
- a source-rig limitation requires changing mesh/armature;
- a requested correction requires weakening a hard anatomical/contact invariant;
- two consecutive iterations trade one major visible defect for another with no net improvement;
- product/gameplay behavior outside the milestone would need to change;
- a tool/environment blocker prevents deterministic evidence generation.

Otherwise continue iterating.
