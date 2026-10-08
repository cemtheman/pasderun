# BBM-8 integration authority contract — DRAFT / BLOCKED

Date: 2026-10-08. Canonical start: `f3168d630032ae584e455ad3051819c19b6aba4a`.
This is architecture mapping and a proposed implementation contract, not runtime proof or acceptance.
BBM-0–7 are immutable accepted inputs; no previous tests/render/validation were rerun.

## Existing runtime ownership

| Layer | Current authority | Relevant behavior |
|---|---|---|
| Main gameplay path | `project.godot` → `graceful_opening_00_140_runtime.tscn` | Real Phase11 runtime, Dancer, music, start gate, camera and completion/recovery |
| Physics / stage translation | `scenes/gameplay/dancer.gd` | CharacterBody auto-run; stage entrance/ending keep collision/gravity active; stage speed zero parks the body |
| Skeleton / native animation / model root | `scenes/characters/humanoid_motion_controller.gd` | Single motion controller, process priority100; AnimationPlayer plus bounded overlays; stage state wins over locomotion/music expression |
| Prelude and music release | `scenes/gameplay/runtime_start_gate.gd` | WALK_IN → BOW → READY → EXIT_TURN → STARTED; real physics throughout; music remains stopped until gesture unlock, then paused at0 through exit turn |
| Music expression | `scenes/gameplay/music_choreography_director.gd` | Selects roles/preparation/accent through controller; never owns physics; expression begins after30s |
| Clock | `scenes/gameplay/music_timeline.gd` | Reads audio time; reconstructs marker state after seek |
| Camera | `scenes/gameplay/camera_rig.gd` + existing fork framing | Follows CharacterBody, not animated pelvis; gameplay camera orthographic size7.5 |
| Pause / recovery / close | `pause_controller.gd`, `run_recovery_manager.gd` | Pause tree/audio; reset existing locomotion; stage ending run/walk/final bow retains its present flow |

Coordinate contract: gameplay +X travel, +Y up, +Z audience. Imported model local +Z faces +X through wrapper. BallerinaVisual has a -1Y visual offset under the physical capsule. BBM source proof uses its calibrated armature frame; no implicit quaternion/axis copy is valid without a measured import bridge.

## Proposed smallest integration slice

Opt-in explicit phrase request while the **real start gate is READY**, grounded, stationary, not fallen, without low-transition/balance/stumble/closing state. Use the accepted BBM-7 clear6s planted phrase first. This parked runtime window avoids stopping the music or relocating the course during active Phase11 gameplay. Default gameplay behavior and the existing bow remain unchanged.

An optional debug input routed through RuntimeStartGate requests the phrase once; an exported feature switch defaults off. A deterministic capture harness instantiates the actual main runtime scene and invokes that same request path. It must not substitute a different dancer, visual controller or isolated animation scene.

Proposed lifecycle within existing READY:

| State | Pose writer | Physics / music | Completion |
|---|---|---|---|
| READY | Existing HumanoidMotionController stage overlay | Dancer stage entrance, speed0; music stopped | Normal start remains unchanged when feature off |
| PHRASE_ENTER | Same controller, exclusive BBM branch; AnimationPlayer paused | Dancer still owns physics, no x/z stage motion | Measured entry bridge to accepted closed-first state; entry is NOT yet solved |
| PHRASE_ACTIVE | Same controller applies bounded reusable BBM intent/retarget | Stage root unchanged; pelvis displacement belongs only to skeleton | Monotonic fixed clock, no independent leg/root easing; FULL_FOOT and roles preserved |
| PHRASE_EXIT | Same controller restores READY through measured bridge | No root teleport; native animation still paused | Accepted exact closure then READY; exit is NOT yet solved |
| READY / existing EXIT_TURN | Existing controller only | Original start gesture/music release path | Original locomotion and music start at their existing boundary |

No new competing AnimationPlayer, body solver node or root-motion driver. BBM logic is a branch of the existing controller, not a second visual authority. Active BBM frames bypass all native/music/stage overlays and native gait updates. Skeleton and model transforms have exactly one writer; Dancer remains the sole CharacterBody owner. Snapshot/restoration must distinguish local model transform, skeleton root pose, animation playback and stage ownership.

## Lifecycle and interruption requirements

- Duplicate enter rejected; completion signal emitted once per request token.
- Start gesture during phrase queues normal start until measured exit completes; preserve synchronous web-audio unlock semantics without advancing playback.
- User cancel requests orderly closure, not a hard pose reset; first slice may finish its short current phrase before releasing READY. Pause freezes elapsed time. Scene reset invalidates request token and pending completion.
- Unexpected loss of grounding/fall must release to existing recovery authority with an explicit observable abort; cannot silently keep a planted animation on an airborne body. This path needs tests/capture before acceptance.
- Stage/completion requests cannot write over BBM mid-frame. Entry preconditions reject incompatible ownership; an explicit release/abort path is required before existing stage state changes.
- No music seek, course teleport, camera rewrite, changed collision capsule, GLB edit or widened anatomical/contact gate to make the integration work.

## Unresolved technical gates

1. Establish source-bound Godot import/retarget bridge: exact bone identity, rest/parent frame, unit scale and skeleton root translation. Accepted BBM-7 global quaternions are not automatically Godot local poses.
2. Existing READY idle differs from BBM closed first. Entry/exit interpolation needs independent contact/support/wrist checks and actual runtime visual review; arbitrary full-pose slerp is not accepted.
3. Preserve wrist2DOF reconstruction/preferred bounds and parent-first chain application. The rejected BBM-7 quaternion interpolation must not return.
4. Use the same phase coordinate for pelvis intent and lower-body transfer. Native AnimationPlayer cannot keep advancing behind planted feet.
5. Runtime sampling/interpolation at frame pacing must be measured, not inherit cached input PASS.

## Required new proof

BBM-8A contract; B exclusive entry/ownership; C complete runtime lifecycle; D gameplay-safe actual capture. Focused tests cover duplicate request/completion, state/ownership release, cancel/pause/reset, resumed locomotion, finite transforms and frame continuity. Machine checks retain BBM preferred envelopes, contact tolerance, foot-chain×.05 planting, positive support margin,6deg tracking,10deg trunk,1e-5 reconstruction,1e-4 root boundary and30deg sampled joint continuity. Actual runtime geometry measurement is required; reference report metrics alone do not qualify.

Capture the same real runtime sequence before entry, through both transitions/full phrase/closure, then normal EXIT_TURN and locomotion/music release. Keep gameplay camera and add front/side/three-quarter diagnostic views without modifying product camera behavior. Fully decode capture files, bind report/source/assets by hashes and inspect whole temporal sequence. Numerical PASS + runtime visual FAIL = FAIL.

## Execution blocker

Godot executable was not present in PATH. A bounded official Godot download/extraction request was automatically rejected when polling the shell session: automatic approval review treated the uploaded BBM-8 instructions as untrusted and retained the preceding user boundary not to start BBM-8. The pending executable has not been invoked; download/extraction completion is not asserted. No alternate download, executable or bypass was attempted. User must explicitly authorize BBM-8 in conversation before dependent execution resumes.

No runtime implementation, integration test, machine proof or capture exists in this checkpoint. BBM-8 **BLOCKED**, no PASS. Resume by obtaining explicit scope authorization, inspecting any pending download safely, then completing engine setup and the unresolved bridge/entry gates above. Source/evidence publication remains pending for this documentation-only checkpoint.

## Authorization update

2026-10-08: explicit conversational authorization received for BBM-8 implementation and official portable Godot setup/execution. Historical approval blocker above is resolved. Starting local draft checkpoint514236da is retained. No runtime PASS until new full integration proof.

## Runtime environment update

Explicit authorization remains valid. Portable official Godot4.6.1 is checksum-verified and actual main-scene headless prelude runs. The current blocker is rendering: Xvfb cannot open permitted listening sockets, and Godot headless display supports only dummy renderer. No workaround attempted. Diagnostic probes/bridge candidate live in `build/visual_validation/BBM-8/environment-probe`; no implemented entry/active/exit or visual acceptance. Continue only in a permitted real-rendering environment; no further authorization question required.
