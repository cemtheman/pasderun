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

## Current engineering status — 2026-10-08

BBM v1 engineering closure is complete within the verified scopes. ENGINEERING PASS != HUMAN ARTISTIC ACCEPTANCE; human artistic acceptance is PENDING. The former Linux Godot4.6.1/Xvfb blocker is superseded by genuine Windows Godot4.7.2 runtime evidence. Earlier stop/blocked/publication notes below are chronology. The current task ends at the human review gate; no next implementation, main merge or deploy. See [closure matrix](BBM_V1_CLOSURE_2026-10-08.md), [human review](BBM_V1_HUMAN_REVIEW_2026-10-08.md), and [design-only roadmap](POST_BBM_V1_ROADMAP.md).

| Milestone | Status | Published reference / evidence |
|---|---|---|
| BBM-0 | PASS | 5c975168; BBM-0/baseline |
| BBM-1 | PASS | 931ef8bd; BBM-1/elbow-path |
| BBM-2 | PASS | 3938f89a; BBM-2 |
| BBM-3 | PASS | 9516b79a; BBM-3 |
| BBM-4 | PASS | d75e1fde; BBM-4 |
| BBM-5 | PASS | 6cb569f5; BBM-5/milestone_report.json |
| BBM-6 | PASS | c32a933e; BBM-6/full-chain-candidate-02/review.md + verification.json |
| BBM-7 | PASS | fb43761f; scoped planted phrase / two styles; BBM-7/candidate-01/review.md + verification.json |
| BBM-8 | PASS | bd26acd4; genuine Windows Godot4.7.2 lifecycle; BBM-8/windows-4.7.2-clear6s/review.md + verification.json |

Evidence paths are relative to build/visual_validation. BBM-6:383 tests PASS;118-time preparation/takeoff/flight/landing machine proof and independent boundary audit PASS; source/manifest integrity and330 image decodes verified; paired three-view strips and BOTH complete118-frame montages actually inspected AI_VISUAL_PASS. Existing candidate-01 landing decision and BBM-0–5 are preserved. Scope: bilateral vertical kinematic jump; human artistic acceptance remains pending. Historical recovery reconstructions are not evidence authority.

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

2026-10-08 scoped engineering PASS: one meaningful planted phrase with clear6s/soft7.2s reusable timing variants; A temporal contract, B support continuity, C coordination and D actual complete temporal/three-view review PASS.194 new samples,12 focused tests, source/evidence integrity. Evidence `build/visual_validation/BBM-7/candidate-01`; render/evidence checkpoint `4204b96fcd537b3cd50edc3f4191e4b2e6a77d88`. Final verification/docs checkpoint resolves via git log on verification.json. Arbitrary distinct choreography and human artistic acceptance are not claimed. BBM-8 remains NOT STARTED.

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

Publication status: full verified118-time source/evidence is LOCAL at e8474f7b86996976219a054a22adb9b0770656ce (tree a4aec5de4475c3ea6f4bcf3272b5c22f6dd27adb). Remote full pack publication stopped on first blob hash mismatch; see journal/handoff. Remote landing checkpoint remains8d508da.

### 2026-10-08 — Exact source/evidence publication complete

- Local start: work/bbm-v1-overnight-20261006, HEAD6566e44b8a53b99fdf4787402901ad4552e3cc66, CLEAN. Remote expected head b987df04684abb5930dff39bc90c18457624ddef confirmed before publication.
- Authoritative verified source/evidence checkpoint e8474f7b86996976219a054a22adb9b0770656ce; exact tree a4aec5de4475c3ea6f4bcf3272b5c22f6dd27adb.
- All357 intended changed paths (59,454,451 bytes) uploaded from immutable Git blob bytes using32766-byte chunks with explicit per-chunk and total byte/base64 length checks. Every GitHub stored blob SHA matched local expected SHA. No shell/base64 pipe or unverified truncated output was used. No hash/tool/stream error occurred in this run.
- Incremental24-entry Git trees assembled; FINAL remote tree exactly a4aec5de4475c3ea6f4bcf3272b5c22f6dd27adb before commit/ref update. Exact remote source/evidence commit: c32a933e0799242d7b5d7ce396a959bd2164d0ec, parent b987df04684abb5930dff39bc90c18457624ddef. Work branch advanced with expected-head lease, fast-forward only.
- Publication COMPLETE. Existing BBM-6 engineering PASS preserved; no tests/render/visual evidence regenerated. BBM-0–5, accepted landing, GLB, hard gates, main and deploy untouched. Earlier transfer-stop notes are historical and resolved by this publication.
- This subsequent documentation-only checkpoint records completion separately so the exact source/evidence tree remains independently addressable at c32a933e0799242d7b5d7ce396a959bd2164d0ec. Its SHA resolves via git log on journal/roadmap after publication. BBM-7/8 remain NOT_STARTED.

### 2026-10-08 — BBM-7 publication complete

BBM-7 scoped engineering PASS exact remote source/evidence checkpoint: `fb43761fd7fa9cf6e27f17565206500bc9bec3d9`; exact verified tree `0622c06b6564e0b138f29bcaa0ac140c76535b86` (same as local `df605f9676a294f9dc3c69f397eee8e926d4c6d8`). All307 changed Git blob SHAs and final tree matched before expected-head branch update. Evidence `build/visual_validation/BBM-7/candidate-01`; actual complete two-style temporal and three-angle AI review recorded in review.md/verification.json. Human artistic acceptance pending; BBM-8 NOT STARTED. BBM-0–6 preserved; no main/deploy/GLB changes.

### 2026-10-08 — BBM-8 blocked before runtime implementation

Canonical start f3168d630032ae584e455ad3051819c19b6aba4a. Existing runtime authorities mapped; draft minimal READY-window accepted phrase lifecycle in docs/BBM8_INTEGRATION_CONTRACT.md. Godot setup automatically rejected because uploaded BBM-8 scope was not treated as explicit authorization superseding prior no-BBM-8 boundary. No bypass. No integration implementation/tests/capture or PASS; BBM-0–7 remain preserved. Resume requires explicit conversational BBM-8 authorization. Documentation-only checkpoint currently local; publication pending.

### 2026-10-08 — BBM-8 runtime capture blocker

User authorization resolved; portable official Godot4.6.1 SHA512 match. Real main scene headless360frame prelude/grounding diagnostic and88bone import/97input-pose bridge candidate archived in `build/visual_validation/BBM-8/environment-probe`. Xvfb cannot open permitted sockets; headless supports dummy renderer only. No real capture/visual proof; lifecycle not implemented/tested. BBM-8 BLOCKED, no PASS. Resume on a rendering-capable permitted environment; authorization persists and accepted BBM-0–7 remain immutable.

BBM-8 BLOCKED diagnostic/source handoff exact remote checkpoint `c000700c1a9e4e171c6fc2aa0e7b444f4cff0e89`, exact tree `6e1302507bdf09621b7f0c6dffd6fc6f7034e2ca` (local `ec8b94aee1776e99192030540591e2e8201f3376`). All17 Git blob SHAs and final tree matched before expected-head update. Publication complete, integration PASS withheld; evidence `build/visual_validation/BBM-8/environment-probe`.


### 2026-10-08 — BBM-8 Windows runtime integration verified

Renderer blocker CLOSED for this permitted Windows environment. Runtime verification and actual gameplay lifecycle capture were performed on Godot 4.7.2.stable.official.ed1daf0bf, Compatibility OpenGL 3.3 / Intel(R) UHD Graphics (Build32.0.101.7084). This is explicitly different from the former Linux Godot4.6.1 diagnostic/headless environment. No Xvfb/headless and no repeat of the old360frame diagnostic. First one-frame real environment evidence was saved before canonical implementation.

Canonical Windows checkout C:/Users/chodo/Documents/pas-de-run was inspected first: local branch motion-studio-v0-6-accepted-arm-visual-probe, HEAD2adb48ec586496d3faa40cec5203798c2df06748; four original untracked roots preserved (build/motion_studio/, build/phase11_3_authored/, build/phase11_3_final_rig/, pas-de-run/). Remote work/bbm-v1-overnight-20261006 confirmed at ee6da0dd58c026fdc0b2d5433192e36e2f4c0704. Separate worktree work/bbm8 on work/bbm8-clear6s-windows-20261008 created from that exact canonical commit. No reset/clean, original checkout branch switch, main merge, push or deploy.

Implemented opt-in READY request in the existing RuntimeStartGate and exclusive existing HumanoidMotionController. Pure pose helper adds no new pose writer. Entry2.4s -> accepted clear6s ACTIVE6s -> exit2.4s -> native EXIT_TURN -> gameplay/music recovery. Native AnimationPlayer freezes during ownership. Actual READY snapshot restored on release; feature defaults OFF. Duplicate/completion token, queued gesture audio unlock, cancel closure, pause, reset invalidation, incompatible states, actual physics grounding loss and stage abort use explicit ownership outcomes.

Source-bound88bone/97sample bridge validates GLB/report hashes, bone identity/parent and global rest origin/basis. Parent-first FK and canonical wrist2DOF reconstruction used. Rejected planted slide replaced by explicit support transfer/swing placement; toes follow each foot target. Common pelvis reach correction preserves leg/foot lengths. Bounded leg-heading search distributes turnout within existing ankle/tracking limits; small positive knee rotation stays below the unchanged flexion-dependent cap. Conservative0.2deg ankle and tracking margins in the solver do not widen audit gates. READY native wrist projection applies only to the opt-in bridge and native READY is restored afterward.

New proof build/visual_validation/BBM-8/windows-4.7.2-clear6s (same bytes as projectless outputs/bbm8_release). Actual main gameplay scene, fixed-fps60 deterministic rendering,730observed frames,647 ENTRY/ACTIVE/EXIT geometric samples,122PNG per view including pre-entry,488fully decoded/hash-bound PNG. All28temporal panels across gameplay/front/side/three-quarter and native-resolution keyframes inspected; scoped AI engineering visual PASS.26/26 focused genuine-runtime checks PASS, including actual loss of floor contact followed by physics recovery. Default feature-OFF original controller/gate canonical-byte fixture comparison over120 EXIT_TURN/gameplay frames: body/bone component error0, state/audio flags equal. No full140s-course, wall-clock performance or human artistic certification is claimed.

Independent actual observed-transform replay on immutable source GLB evaluated skin (no Blender render or accepted evidence regeneration): no failures across existing preferred joint envelopes, wrist reconstruction, derived knee cap, contact/planting/support, tracking, trunk, hand-mesh gap, segment lengths and continuity. Worst contact0.002872 <0.011715; planting0.003552 <0.009763; support margin minimum0.001243 >0; tracking4.721deg <6; trunk8.889deg <10; reconstruction7.451e-6 <1e-5; sampled joint change4.769deg <30. Phase root boundaries8.345e-7/4.278e-5/6.426e-5 <1e-4. Physical body/model root remain unchanged throughout the phrase; ordinary native gait follows release.

Earlier rejected probes (sliding, contact/support, reach, ankle) retained separately and never relabeled PASS. Final source/asset/executable/runtime/capture/test hashes in verification.json and capture_manifest.json. BBM-0–7, GLB, anatomical/contact hard-gate definitions, accepted evidence and product camera/physics assets remain byte-for-byte unchanged in Git. BBM-8 scoped engineering PASS only after real lifecycle + visual review + focused regression proof. Feature remains opt-in; human artistic acceptance pending. Exact local checkpoint recorded in subsequent documentation marker; remote canonical branch remains unchanged.


### BBM-8 exact local runtime/source checkpoint

Scoped engineering PASS checkpoint: `bd26acd4ea7c113c253278fa696db4bd0ba57ced`, exact parent `ee6da0dd58c026fdc0b2d5433192e36e2f4c0704`, branch `work/bbm8-clear6s-windows-20261008`. Genuine Windows Godot4.7.2 lifecycle, numeric audit,26 focused tests,488 PNG/28-panel visual inspection and scoped default regression are archived at `build/visual_validation/BBM-8/windows-4.7.2-clear6s`. This subsequent documentation marker records the independently addressable source/evidence commit. No remote update, main merge or deploy.


### 2026-10-08 — BBM v1 engineering closure / human artistic gate

- BBM-0–8 scoped ENGINEERING PASS. ENGINEERING PASS != HUMAN ARTISTIC ACCEPTANCE; human artistic acceptance remains PENDING. Final closure matrix and claims/limits: `docs/BBM_V1_CLOSURE_2026-10-08.md`.
- Native remote work branch `work/bbm-v1-overnight-20261006` verified at `214f41204d07292230e9ffc79db89ee9adbc860f`. Direct parent/source checkpoint `bd26acd4ea7c113c253278fa696db4bd0ba57ced`, exact source tree `cadaa0ead53d6d5c64ff7bc47ad032120a05aaf4`. Native Git publication is COMPLETE and supersedes failed API/blob-transfer and pending-publication notes. No repeat source/evidence publication.
- Historical Linux Godot4.6.1/Xvfb blocker superseded by genuine Windows Godot4.7.2 Compatibility/Intel UHD proof: entry→clear6s active→exit→gameplay/music recovery, one HumanoidMotionController authority,26/26 runtime tests,647 geometry samples,488 PNG/four-view actual engineering review, scoped default regression difference0. No full140s course claim.
- Read-only history/manifest audit: exact milestone references resolve as ancestors; accepted binary evidence hashes match; GLB remains baseline SHA256 a162d8730238a76ba1d6b31910c98fb1f5640c46917983e0bbad04095e81b7b2. Existing hard gates and BBM-0–7 preserved. Ten BBM-8 raw-text binding differences in fresh clones are fully explained by CRLF/mixed-line-ending clean normalization: all12 original Windows verification hashes match exactly, and all12 original/committed files match after CRLF→LF. Additional provenance mapping is in the closure; accepted verification/evidence stays unchanged.
- No rerender/retest or new mechanics/gameplay. Separate local closure branch/worktree preserves the original Motion Studio branch/HEAD/untracked files and original BBM-8 worktree. Main remote verified `080d42cb076a0efcc4902bbef7d9e42aae5550e3`; no main merge, deploy or next implementation.
- Human pack: `docs/BBM_V1_HUMAN_REVIEW_2026-10-08.md`; practical accepted GIF/strip/keyframe links only. Design-only next roadmap: `docs/POST_BBM_V1_ROADMAP.md`, prioritizing human acceptance→distinct vocabulary→cross-family transitions→existing musical composition→selective Phase11 course integration→production validation. No invented BBM-9.
- Publish only the documentation-only descendant of starting HEAD with native Git and exact expected-head safety, after diff/allowed-path checks; verify final remote HEAD. Resulting closure documentation SHA resolves via `git log -1 --format=%H -- docs/BBM_V1_CLOSURE_2026-10-08.md`. Independent BBM-8 source/evidence checkpoint is unchanged.
- Stop at human review. Main integration requires human artistic acceptance, explicit merge decision, defined integration scope and rollback point. Main merge NO; deploy NO.
