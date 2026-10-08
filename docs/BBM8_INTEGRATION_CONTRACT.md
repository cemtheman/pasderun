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


### 2026-10-08 — BBM-8 Windows runtime integration verified

Renderer blocker CLOSED for this permitted Windows environment. Runtime verification and actual gameplay lifecycle capture were performed on Godot 4.7.2.stable.official.ed1daf0bf, Compatibility OpenGL 3.3 / Intel(R) UHD Graphics (Build32.0.101.7084). This is explicitly different from the former Linux Godot4.6.1 diagnostic/headless environment. No Xvfb/headless and no repeat of the old360frame diagnostic. First one-frame real environment evidence was saved before canonical implementation.

Canonical Windows checkout C:/Users/chodo/Documents/pas-de-run was inspected first: local branch motion-studio-v0-6-accepted-arm-visual-probe, HEAD2adb48ec586496d3faa40cec5203798c2df06748; four original untracked roots preserved (build/motion_studio/, build/phase11_3_authored/, build/phase11_3_final_rig/, pas-de-run/). Remote work/bbm-v1-overnight-20261006 confirmed at ee6da0dd58c026fdc0b2d5433192e36e2f4c0704. Separate worktree work/bbm8 on work/bbm8-clear6s-windows-20261008 created from that exact canonical commit. No reset/clean, original checkout branch switch, main merge, push or deploy.

Implemented opt-in READY request in the existing RuntimeStartGate and exclusive existing HumanoidMotionController. Pure pose helper adds no new pose writer. Entry2.4s -> accepted clear6s ACTIVE6s -> exit2.4s -> native EXIT_TURN -> gameplay/music recovery. Native AnimationPlayer freezes during ownership. Actual READY snapshot restored on release; feature defaults OFF. Duplicate/completion token, queued gesture audio unlock, cancel closure, pause, reset invalidation, incompatible states, actual physics grounding loss and stage abort use explicit ownership outcomes.

Source-bound88bone/97sample bridge validates GLB/report hashes, bone identity/parent and global rest origin/basis. Parent-first FK and canonical wrist2DOF reconstruction used. Rejected planted slide replaced by explicit support transfer/swing placement; toes follow each foot target. Common pelvis reach correction preserves leg/foot lengths. Bounded leg-heading search distributes turnout within existing ankle/tracking limits; small positive knee rotation stays below the unchanged flexion-dependent cap. Conservative0.2deg ankle and tracking margins in the solver do not widen audit gates. READY native wrist projection applies only to the opt-in bridge and native READY is restored afterward.

New proof build/visual_validation/BBM-8/windows-4.7.2-clear6s (same bytes as projectless outputs/bbm8_release). Actual main gameplay scene, fixed-fps60 deterministic rendering,730observed frames,647 ENTRY/ACTIVE/EXIT geometric samples,122PNG per view including pre-entry,488fully decoded/hash-bound PNG. All28temporal panels across gameplay/front/side/three-quarter and native-resolution keyframes inspected; scoped AI engineering visual PASS.26/26 focused genuine-runtime checks PASS, including actual loss of floor contact followed by physics recovery. Default feature-OFF original controller/gate canonical-byte fixture comparison over120 EXIT_TURN/gameplay frames: body/bone component error0, state/audio flags equal. No full140s-course, wall-clock performance or human artistic certification is claimed.

Independent actual observed-transform replay on immutable source GLB evaluated skin (no Blender render or accepted evidence regeneration): no failures across existing preferred joint envelopes, wrist reconstruction, derived knee cap, contact/planting/support, tracking, trunk, hand-mesh gap, segment lengths and continuity. Worst contact0.002872 <0.011715; planting0.003552 <0.009763; support margin minimum0.001243 >0; tracking4.721deg <6; trunk8.889deg <10; reconstruction7.451e-6 <1e-5; sampled joint change4.769deg <30. Phase root boundaries8.345e-7/4.278e-5/6.426e-5 <1e-4. Physical body/model root remain unchanged throughout the phrase; ordinary native gait follows release.

Earlier rejected probes (sliding, contact/support, reach, ankle) retained separately and never relabeled PASS. Final source/asset/executable/runtime/capture/test hashes in verification.json and capture_manifest.json. BBM-0–7, GLB, anatomical/contact hard-gate definitions, accepted evidence and product camera/physics assets remain byte-for-byte unchanged in Git. BBM-8 scoped engineering PASS only after real lifecycle + visual review + focused regression proof. Feature remains opt-in; human artistic acceptance pending. Exact local checkpoint recorded in subsequent documentation marker; remote canonical branch remains unchanged.
