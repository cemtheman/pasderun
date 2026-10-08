# Pas de Run after BBM v1 — design only

2026-10-08. No implementation begins in this closure task. Human acceptance of the scoped BBM v1 foundation is the first dependency. This proposal does not create BBM-9 or an unconditional BBM v2 program.

## What the evidence proves and leaves isolated

[BBM v1 closure](BBM_V1_CLOSURE_2026-10-08.md) proves the accepted upper-body path, upstream turnout, conservative foot semantics, observed support/contact proxies, planted plie/weight transfer, one bilateral vertical jump chain and one planted phrase with two timing/style variants. BBM-8 transfers that planted clear6s phrase into the real main scene under one controller, with measured transitions and recovery.

The proof remains narrow: no arbitrarily distinct phrase set, no reusable transitions across phrase families, no moving-course BBM choreography, no full140s course visual certificate, no wall-clock performance or production export proof. READY is stationary and music is not advancing during the BBM slice. clear6s/soft7.2s alone do not establish vocabulary diversity. The jump proof has not been promoted into BBM-8 gameplay.

## Existing project architecture and terminology

The journal's safe product baseline is Phase11.2, main `080d42cb076a0efcc4902bbef7d9e42aae5550e3`. `project.godot` selects `scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn`. Dancer owns CharacterBody physics; HumanoidMotionController owns skeleton/native animation/model pose; RuntimeStartGate owns prelude and music release. MusicTimeline reads the audio clock and rebuilds marker state after seek. MusicChoreographyDirector is the existing Phase9 music-to-body bridge: role/action preparation/accent selection through the visual controller, activation after30s, and `data/music/graceful_opening.visual_score_v0_1.json`. The player retains action decisions. Camera, pause, recovery and ending remain existing product authorities.

BBM-7 already provides a temporal/style contract (`docs/BBM7_PHRASE_CONTRACT.md`, `tools/ballet_motion/phrase_v1.py`, `tools/blender/bbm_phrase_runtime_v1.py`). It schedules bounded intent; it does not license cached input PASS for new compositions. BBM-8 exposes the smallest opt-in lifecycle under existing ownership (`docs/BBM8_INTEGRATION_CONTRACT.md`). Extend these authorities instead of installing a competing solver/controller/clock.

Motion Studio remains a separate authoring/reference branch, not a ready production import. Read-only history inspection of `85e7de2f1854830d1f4f873d5392177f07c54173:MOTION_STUDIO_CHECKPOINT.md` identifies eight arm candidates/14 directed clips, a foot catalog, measured crown hand overlaps, incomplete foot proof and no coordinated whole-body/export acceptance at that historical checkpoint. The local Motion Studio branch is now `2adb48e...`, with later experimental First Position work. Do not treat historical catalog counts or later experiments as current accepted vocabulary. BBM's journal explicitly distinguishes the safe GLB from a later different Motion Studio GLB; asset substitution requires its own decision.

The next natural work is **vocabulary and choreography on the BBM foundation**, followed by **Phase11 course integration/validation**. Motion Studio → gameplay authoring can support that work once contracts are proven. Reserve **Ballet Body Model v2** for measured model-level gaps that cannot be handled by existing intent/support/retarget layers. There is no repository evidence here establishing a canonical next phase number; do not invent Phase12 as settled policy.

## Dependency-ordered proposal

| Step | Smallest concrete result | Dependency and exit evidence | Ownership / boundary |
|---|---|---|---|
| A. Human acceptance gate | User accepts BBM v1 as foundation or identifies exact artistic revisions | Review A–E in the human pack; record HUMAN_ACCEPT/REVISE and any stylistic preference. Resolve foundational revisions before scaling. | Human decision; no automatic acceptance or merge |
| B. Vocabulary proof | After acceptance, choose one genuinely distinct, product-relevant phrase family; then establish a small multi-family set | Prefer a measured demi-pointe/releve phrase first because BBM-3 has static foot proof while BBM-7 is FULL_FOOT. Human selection must confirm product need. Measure support-area transition, entry/closure, anatomy/contact/planting and whole temporal/three-view quality anew. Separately consider the existing jump chain as another family, not already certified runtime motion. | Choreography/vocabulary over existing mechanics; model work only for a demonstrated gap |
| C. Transition library | One reusable supported transition between accepted phrase families, plus cancellation/recovery semantics | B families accepted; explicit start/end support/contact/root signatures, musical bounds and independent transition tests/review. No arbitrary whole-pose interpolation or hidden rest reset. BBM-8's READY bridge is a useful measured example, not a general library. | Transition/ownership contracts; keep Dancer and controller authority |
| D. Choreography composition | A short sequence of accepted families under existing musical/gameplay timing | C transitions; extend the existing visual score/phrase schedule with explicit duration, contact/load roles, interruptibility and closure. Verify exact boundaries, new composed samples and full visual sequence. Require at least two distinct families, not only restyled clear6s. | MusicTimeline/Director select intent; controller realizes it; player owns actions |
| E. Selective course integration | One chosen real Phase11 window with advancing music and gameplay, then progressively more course coverage | D composed proof; user chooses integration scope. First inspect upcoming player actions, grounding, camera and interruption budget. Validate real scene before/through/after insertion and default baseline. Preserve ending/prelude/topology. Expand to entire140s only after this slice passes. | Separate gameplay integration from body-model changes; opt-in and rollback |
| F. Production motion validation | Defined target-platform course/export/recovery certificate | E coverage; measured wall-clock frame time/resource costs, interruptions/falls/pause/reset/seek/ending, product camera, music continuity, default regression and target export/runtime checks. Human whole-course review and explicit main merge decision remain required. | Existing runtime authorities, intended shipping renderer/platform; no deployment in this proposal |

This is a dependency proposal, not approval to implement every step. The smallest next product-relevant capability is a **second distinct accepted phrase with explicit support transitions**, selected after human review. That tests generality before course-scale composition. If human review rejects the current foundation, the next work is scoped revision of that foundation instead.

## Layer boundaries and authoring pipeline

Model-level: canonical semantics, preferred/hard envelopes, upstream turnout, foot calibration, contact/support observations, retarget reconstruction and invariant checks. A limitation requiring new rig segmentation, dynamic balance/force modeling or changed solver authority belongs in a separately scoped BBM v2 proposal; do not hide it inside choreography.

Vocabulary/choreography: phrase intent, support/contact signatures, timing/style, entry/exit conditions and family composition. Gameplay: scheduling against the existing music clock, player-action ownership, interruption/recovery, camera and course integration. Performance/export belong to production validation, not proof from a fixed-fps GIF.

Motion Studio authoring should eventually emit the same source-bound intent/contact/temporal contract used by accepted BBM phrases, with rig/GLB/calibration hashes, explicit units/coordinate frames, duration and support roles. The runtime importer must reject incompatible assets or unsupported contact states. First prove one accepted authored phrase has parity through the existing bridge; do not bulk-import draft Actions, failed crown clips or a different GLB. Choose an authoring schema only after B–C establish reusable family/transition contracts, or earlier only if actual authoring cost demonstrably blocks that smallest proof.

## Human review before scaling

Required decisions: accept/revise BBM v1; choose the next phrase family and desired artistic character; review the first new family and first cross-family transition; accept the composed musical exercise; review product-camera integration and whole-course evidence before main. Finite machine/AI PASS never fills these human fields.

Before any main integration require explicit merge decision, human artistic acceptance, defined integration scope and rollback point. Keep `214f412...` as pre-closure documentation rollback and `bd26acd...` as independent BBM-8 source/evidence reference; later implementation must define its own exact safe baseline.

## Deliberately deferred

Full force/tissue simulation and medical claims; arbitrary ballet completeness; free turns/traveling jumps/en-pointe without specific proof; wholesale rig/GLB replacement; automatic choreography generation; bulk catalog import; full-course BBM substitution; renderer/platform generalization and deployment before defined validation. Do not weaken gates to make a new family fit the old model.

Next implementation remains **NOT STARTED**. The closure ends at documentation publication and the pending human review gate.
