# BBM-1 engineering review — AI_VISUAL_REVISE

BBM-1 is NOT complete. BBM-2..8 have not started. Active successful milestone remains BBM-0; all BBM-1 experiments remain isolated from gameplay.

## Actual evidence inspected

- Historical diagnostic FRONT / THREE_QUARTER / SIDE strip at 1/13/25/37/49 (MACHINE_FAIL wrist gate, explicitly marked).
- Coordinated, shaped, phrase, transported and elbow-plane candidate three-view strips at the same grid.
- Final `candidate/verified_frame_strip.png` and `candidate/opening_continuity_29_40.png`.
- Latest `opening-hand-line/verified_frame_strip.png` and `opening-hand-line/opening_continuity_29_40.png`.
- All 49 preview images are decoded and retained; GIF playback is a 24-fps diagnostic grid, not authored music timing. Review relied on actual frame strips/montages, not an assertion that the GIF was watched.

## Findings

Shoulder roots remain low and the neck remains free within clothing/hair occlusion. Elbow bend stays rounded relative to the angular safe-main baseline. Finger-only shaping removes obvious splay. The two-DOF wrist gate now passes without independent axial wrist rotation. Root and foot/toe anchors stay unchanged.

However, all-sample evidence exposes inappropriate palm rotation during opening. The endpoint/timing correction tradeoff remains unresolved: parallel transport avoids 50–62-degree orientation jumps but leaves end palms too frontal; elbow-plane fitting restores end appearance but still has unwanted mid-phrase palm turning; intermediate hand-line correction reduces the wrist break but produces visibly upward-facing, offering/scoop-like palms around 75%. This does not preserve the accepted phrase's visual character.

Classification: **retarget / ballet technique / timing**. Smallest correction layer: coupled upper-arm/forearm/wrist orientation and explicit palm-plane intent. Finger curl, camera, source weights and mesh are not the appropriate correction layers.

## Verdict and stop

**AI_VISUAL_REVISE**. Automated gates are necessary but did not establish visual quality. The last two attempts exchange wrist/palm defects without a clearly acceptable whole phrase. Stop condition **5** applies; no milestone promotion, invariant relaxation or gameplay integration.

No user aesthetic choice is forced yet. Next engineering step: add explicit source-bound palm-normal targets at the reviewed phrase anchors and through opening, then solve them jointly with elbow/forearm/wrist within the unchanged envelopes. Include frames 29–40 in the gate; keep the exact accepted source GLB, contact roots and length invariants.
