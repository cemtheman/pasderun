# BBM-1 elbow-path review

Verdict: **AI_VISUAL_PASS**, provisional engineering regression acceptance.

Compared with the identical-camera historical diagnostic strip (which retains its failed wrist gate), the candidate reduces finger splay and abrupt wrist breaks. The sampled historical elbow bend-pole arc preserves the opening carriage better than endpoint-linear poles. All 49 front frames were inspected, including preparation and complete opening montages; no sudden palm inversion is visible. Three-quarter and side keyframes retain rounded arms and continuous hand lines. Shoulder carriage stays low with available neck space; clavicle/head offsets remain restrained. The preparation/first-position elbows retain the source reference's angular low-poly appearance, rather than introducing a new major regression.

49/49 implemented geometric samples PASS; 349 tests PASS. Root/foot/toe anchors unchanged, source GLB digest unchanged. Palm direction is reviewed visually, supplemented by explicit normal-error diagnostics, rather than inferred from endpoint tests. This PASS is relative to accepted arm v0.6, not a claim of production-ready whole-body ballet, clinical anatomy or final artistic acceptance.

Limitations: hair and costume obscure scapular/neck details; no independent scapula or calibrated eye bone, so those fields remain semantic/head-coupled. Preview uses the fixed 49-sample review grid at 42ms/frame, not a new gameplay duration. BBM-8 integration has not occurred.

Reproduce: `python3 tools/visual_validation/run_bbm1_evidence.py --blender <blender> --variant elbow-path`.
