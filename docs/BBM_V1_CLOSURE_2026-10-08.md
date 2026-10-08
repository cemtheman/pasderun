# Ballet Body Model v1 engineering closure — 2026-10-08

BBM-0–8: **ENGINEERING PASS** within the recorded scopes. **ENGINEERING PASS != HUMAN ARTISTIC ACCEPTANCE**. Human artistic acceptance: **PENDING**. Visual engineering decisions are AI_VISUAL_PASS; BBM-0's decision applies only to baseline reproducibility. No human decision is inferred from these gates.

Canonical branch: `work/bbm-v1-overnight-20261006`. Starting remote/documentation HEAD: `214f41204d07292230e9ffc79db89ee9adbc860f`.
Independently addressable BBM-8 source/evidence checkpoint: `bd26acd4ea7c113c253278fa696db4bd0ba57ced`; exact source tree: `cadaa0ead53d6d5c64ff7bc47ad032120a05aaf4`.
`214f412...` has that source checkpoint as its direct parent; its tree is `6ec115beddb1982e323bf0906393059707faa1c7` and its changes are documentation only (including the existing REPORT.md marker).

## Closure matrix

Evidence links below refer to committed records; test numbers are existing results, not new test runs. Machine verification, visual engineering review and human artistic acceptance remain separate.

| Milestone | Purpose | Engineering status | Canonical checkpoint | Evidence | Primary gate | Known limitation | Human acceptance |
|---|---|---|---|---|---|---|---|
| BBM-0 | Baseline evidence lock | PASS (scoped) | `5c9751685660348f6509f2d104d4251ce3391e38` | [review](../build/visual_validation/BBM-0/baseline/review.md) | 304 baseline Python tests; 18/18 static render cells and geometry PASS | Inherited poses locked, not artistically endorsed | PENDING |
| BBM-1 | Upper-body / palm / elbow coordination | PASS (scoped) | `931ef8bd9e3353e0e65c4cd087cdc6e56b051796` | [review](../build/visual_validation/BBM-1/elbow-path/review.md) | 349 tests; 49/49 geometric samples; full front sequence + three views PASS | Semantic scapula; gaze=head; finite timing grid | PENDING |
| BBM-2 | Distributed turnout and stance alignment | PASS (scoped) | `3938f89aff2cab5504a7d070f3f420d04c8fb035` | [review](../build/visual_validation/BBM-2/review.md) | 353 tests; 18 paired cells; tracking <=4.94 degrees <6; three views PASS | Single-toe proxy; arch/pronation unobservable; partial turnout fifth | PENDING |
| BBM-3 | Foot / demi-pointe / pointe-ready semantics | PASS (scoped) | `9516b79a76b9a687dc32b4225df8c85a109cb3d7` | [review](../build/visual_validation/BBM-3/review.md) | 358 tests; 18 paired cells; calibrated ankle/local/world/contact gates and visual PASS | Open pointe-ready preparation; no full en-pointe; semantic arch/hindfoot | PENDING |
| BBM-4 | Support / balance / asymmetry | PASS (scoped) | `d75e1fde9b49f3839302a03392ec2a47622d4da4` | [review](../build/visual_validation/BBM-4/review.md) | 362 tests; 24 paired cells; positive static margins; visual PASS | Surface-density COM/contact proxies; no tissue mass or dynamic balance claim | PENDING |
| BBM-5 | Plie and planted weight transfer | PASS (scoped) | `6cb569f503dc765beb26466d19fb0d9c7ca1c133` | [review](../build/visual_validation/BBM-5/review.md); [milestone report](../build/visual_validation/BBM-5/milestone_report.json); [transfer review](../build/visual_validation/BBM-5/weight-transfer/review.md) | 369 tests; 49 plie +25 transfer samples; footprint/plant/support and both visual subproofs PASS | Quasistatic support eligibility; TOUCH does not measure zero load | PENDING |
| BBM-6 | Preparation / takeoff / flight / landing | PASS (scoped) | `c32a933e0799242d7b5d7ce396a959bd2164d0ec` | [review](../build/visual_validation/BBM-6/full-chain-candidate-02/review.md); [verification](../build/visual_validation/BBM-6/full-chain-candidate-02/verification.json) | 383 tests; 118/118 samples; independent boundary audit; both complete montages +3-view review PASS | Bilateral vertical kinematics; static arms; no force simulation or jump library | PENDING |
| BBM-7 | Reusable phrase timing and style | PASS (scoped) | `fb43761fd7fa9cf6e27f17565206500bc9bec3d9` | [review](../build/visual_validation/BBM-7/candidate-01/review.md); [verification](../build/visual_validation/BBM-7/candidate-01/verification.json) | 12 focused tests; 194/194 samples; two whole sequences +three views PASS | One planted phrase, clear6s/soft7.2s variants; not distinct choreography | PENDING |
| BBM-8 | Single-authority gameplay lifecycle | PASS (scoped) | `bd26acd4ea7c113c253278fa696db4bd0ba57ced` | [review](../build/visual_validation/BBM-8/windows-4.7.2-clear6s/review.md); [verification](../build/visual_validation/BBM-8/windows-4.7.2-clear6s/verification.json) | 26/26 runtime tests; 647 geometry samples; 488 PNG/four views; scoped default regression difference=0 | Opt-in READY window; fixed-fps capture; no full140s course/performance/export certification | PENDING |

## Read-only audit and preserved policy

The four authoritative methodology/contract documents, final BBM-6/7/8 reviews and verification records, older handoffs, runtime report and accepted manifests were read. Complete canonical branch history was fetched through native Git; every matrix checkpoint resolves exactly and is an ancestor of the starting HEAD. BBM-6 canonical publication `c32a933...` has tree `a4aec5de4475c3ea6f4bcf3272b5c22f6dd27adb`; BBM-7 `fb43761...` has tree `0622c06b6564e0b138f29bcaa0ac140c76535b86`. Their original local checkpoint mappings remain in the journal.

File SHA256 checks found no mismatch in BBM-1 continuation (98 files), BBM-2 (63), BBM-3 (46), BBM-4 (33), BBM-5 plie (138), BBM-5 transfer (107), BBM-6 (332), BBM-7 (281), or BBM-8 capture (488) manifest entries. These totals include reports/composites and historical entries, not only raw images. BBM-0's geometry-report hash matches its baseline manifest. BBM-6's four verification bindings and BBM-7's eleven source/report/review bindings match. BBM-5's full milestone report preserves the separate plie and transfer decisions. Immutable generator NOT_REVIEWED statuses in BBM-6/7 are intentionally complemented by their subsequent review.md/verification.json, not rewritten.

All nine milestone trees preserve the baseline GLB Git blob. Current source GLB SHA256 is `a162d8730238a76ba1d6b31910c98fb1f5640c46917983e0bbad04095e81b7b2`. The BBM-8 delta against `ee6da0dd...` leaves BBM-0–7 evidence, `assets/ballet_motion`, `tools/ballet_motion`, and the GLB unchanged. Existing preferred/hard anatomical limits, contact policy, 6-degree tracking, 10-degree trunk, 1e-5 reconstruction, 1e-4 boundary root and 30-degree sampled continuity remain as recorded in the applicable proofs. New stricter checks did not authorize weakening old gates.

Native `ls-remote` confirmed canonical work HEAD `214f412...` and main `080d42cb076a0efcc4902bbef7d9e42aae5550e3` at closure start. The original Motion Studio checkout and original BBM-8 worktree were not switched/reset/cleaned. Closure uses a separate clean worktree, local branch `work/bbm-v1-closure-20261008`. Only documentation is to be committed/pushed to the canonical work ref. No deployment command or workflow was invoked; this is a repository/history audit, not an external deployment-platform audit.

No BBM-8 rerender, runtime retest or accepted evidence regeneration was performed. A raw-text hash discrepancy was investigated read-only and fully resolved as Git line-ending normalization, as documented below. No behavioral integrity contradiction remains.

## BBM-8 text hash provenance

The existing verification.json binds raw files from the original Windows capture checkout. Ten text bindings differ from newly checked-out/committed LF blobs. All twelve verification bindings match the original Windows files exactly, and **all twelve original and committed files are byte-identical after CRLF-to-LF normalization**. The two new GDScript files had mixed line endings in the original checkout; blindly converting every LF to CRLF does not reproduce their raw hashes. The original checkout remains clean in Git because clean-filter normalization produces the committed blobs. Source snapshots have the same committed normalized content. Preserve the accepted verification record; use the following additional provenance mapping when auditing fresh clones.

| Bound text path | Original verification SHA256 | Committed LF blob SHA256 |
|---|---|---|
| `scenes/characters/bbm8_pose_math.gd` | `84dae236af99d7544680cc69d1132229377cb3eaea17e589e7794f5e28617253` | `1649e5a76007324c8335686bffea1f5a5d62819cbea91216654a434aa1649e8e` |
| `scenes/characters/humanoid_motion_controller.gd` | `01409ef7757ce68d09e01994e8e43d9e9779228cfe64731f2e470941a99b51d5` | `761f696299769a95bd30e9b18d2e82a1405dca2106beb4a764c77de4dfb2ff13` |
| `scenes/gameplay/runtime_start_gate.gd` | `dfa2555d4455b6fdf784fd97336c6a371d58755eaf8db667733321145b3b66c1` | `63359119a76213ef44f918a0fce6c23aa97aa466b92946ccb1b2042a48604057` |
| `tools/godot/bbm8_integration_harness.gd` | `e5ac76d965d5af2db4d24f6729f2964365738a978fd57618202ebc1e873e4455` | `628f40f10c5a83c467a53250ea3ba6fdec516c807e8582db11e033faa470e723` |
| `tools/godot/audit_bbm8_runtime_geometry.py` | `e5196804e563f4af4f122592d7c97bae636af754885c268ed41a5d602ec0d305` | `318a3db8abd15f42a21f12224595695d576b2a0fae58fde49d1364dc7d3e16e4` |
| `tools/godot/build_bbm8_runtime_payload.py` | `51cda5e51d7d19655322de702dec17c7d9ebe29a3fbbef8bf9c6e791bcc13c12` | `369330a1ec111f1cba5888b3fef9e7221c742db26d88c707e088ac282fd2c5fe` |
| `assets/bbm8/clear6s_runtime_candidate.json` | `e012e9a7ed975f0eb60316f641fe707e1cafcb581df63e117d8e35435681c55e` | `5b8e1fc350f0d35af422040823bc0cc8e6b9b275a890fd0a171d39ddbd7f70b9` |
| `build/visual_validation/BBM-8/windows-4.7.2-clear6s/capture_manifest.json` | `14d7ddab399c6a5eba93faa3288321e407a85dac736e61591b01a9ff2f0f20fb` | `ac54f41f6dd21b0bedfc9b94c6c5faea5b6d8cbda12707b822f4999b0d56d8c7` |
| `build/visual_validation/BBM-8/windows-4.7.2-clear6s/geometry_audit.json` | `7979b7d1a2c38606aac109acab1abc9caee21370ae99e843555a29c2344984ad` | `1847826ad284894c0e0a1b6a878ffadd710a66e0c496c510a7aad3bc0607ec10` |
| `build/visual_validation/BBM-8/windows-4.7.2-clear6s/review.md` | `ffabd153a420798b556a46407ab63647241f8858146149b9024bae594143059e` | `5323f8876958d1dd0d31f9f286089bf5d0fbb529dbc834865ee61bda20a31ba5` |

The 488 PNG hashes are exact, without text normalization. runtime.json and focused_tests/runtime.json also match exactly. This mapping explains provenance; it does not replace raw-file hashes or relax motion gates.

## Publication and superseded blockers

Native Git publication of BBM-8 is complete: the remote work HEAD was already exactly `214f412...`; the older `ee6da0dd...` value is historical. No repeat source/evidence upload is needed. Native publication supersedes failed API/blob-transfer attempts and pending-publication notes; their chronology is retained.

The Linux Godot4.6.1/Xvfb rendering blocker is superseded by genuine Windows Godot4.7.2 Compatibility/Intel UHD runtime evidence: real main scene, entry2.4s → clear6s active → exit2.4s → native EXIT_TURN → gameplay/music recovery; no Xvfb/headless. Existing single HumanoidMotionController authority is retained. Default-OFF comparison covers 120 EXIT_TURN/gameplay frames with body/bone difference0 and equal state/audio flags. It does not certify the whole course.

This closure's documentation checkpoint is the commit introducing this file; resolve its exact SHA with `git log -1 --format=%H -- docs/BBM_V1_CLOSURE_2026-10-08.md`. Publish only as a descendant of `214f412...`, using an exact expected-head lease, then verify remote HEAD. The separately addressable BBM-8 source/evidence commit remains unchanged.

## Final scope statement

BBM v1 supports reusable ballet-readable body mechanics within these proofs: upstream distributed turnout semantics, observed support/contact reasoning, plie and planted weight transfer, deterministic bilateral vertical jump chain, phrase-level timing/style composition, genuine opt-in gameplay integration through one motion authority, deterministic visual validation, and scoped regression-preserving integration.

BBM v1 does **not** claim full biomechanical force simulation, complete ballet vocabulary, arbitrary choreography, dancer-specific medical/clinical validity, production-wide gameplay certification, full 140-second course visual certification, final human artistic approval, or production deployment. Rig segmentation, costume/hair occlusion, finite samples, practical COM/contact proxies and platform/render scope remain limitations.

## Handoff boundary

Review [the human pack](BBM_V1_HUMAN_REVIEW_2026-10-08.md), then choose HUMAN_ACCEPT or REVISE. [Post-BBM v1 roadmap](POST_BBM_V1_ROADMAP.md) is design only. No BBM-9, new mechanics or next implementation phase starts here.
Before main integration: human artistic acceptance, explicit merge decision, defined integration scope, and rollback point are all required. Main merge: NO. Deploy: NO.
