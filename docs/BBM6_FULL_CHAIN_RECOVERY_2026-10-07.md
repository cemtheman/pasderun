# BBM-6 full-chain source reconstruction after second cloud transport failure

Base verified source/evidence checkpoint: 8d508da0206ce3ae61ba2495a2f830c6366bc0f5.
This branch archives six files reconstructed from the authorized visible tool inputs after exec-server transport disconnected. Original local file SHA equality is NOT VERIFIED. The runner/audit formatting has been reconstructed; do not assert byte identity. These files are a reproduction starting point, not an accepted full BBM-6 checkpoint.

Observed before interruption:
-230 ballet-motion +108 Blender +45 Motion Studio tests PASS (383 total).
-full-chain-candidate-02:118 candidate times MACHINE_PASS, zero failures.
-independent measured chain audit PASS; maximum boundary root step4.548579454421997e-6 <1e-4.
-min sampled airborne foot clearance6.075200508348644e-5; min ground support margin0.00030275831884868864; chest max9.808887601021379deg; shortest joint step8.037245869419968deg.
-actual paired takeoff/flight, preserved-landing and main three-view strips viewed. Full118-frame montage review was interrupted before completion. Formal AI report remained NOT_REVIEWED; general BBM-6 PASS is withheld.

Existing candidate-01 landing assessment/evidence is preserved on base checkpoint. Final source/evidence remained owned local uncommitted work in /workspace/scratch/c6d02bfb87a4/pasderun; survival, clean tree and generated evidence persistence are unknown while execution is unavailable.

Corrections: exact release .35 remains TAKEOFF;118-time dense grid includes exact boundaries plus1e-6 neighbourhoods; ankle30deg push→40deg apex→25deg contact within existing range; solved flat-contact inversion transported under (1-rise) instead of discarded. Existing knee8→32landing absorption, pelvis/trunk/arm intent preserved. Initial dense probe had two real flight penetration failures; subsequent sole parameter probe and final dense render corrected them without changing thresholds.

Next: recover cloud execution; inspect/preserve original owned files first. Reconcile source hashes against original full-chain-candidate-02 report, verify PNG/GIF/source/manifest integrity, complete paired all118 actual visual review and rerun tests/syntax/diff. Use these reconstructed files only if originals are lost, then regenerate evidence in a fresh folder:
python3 tools/visual_validation/run_bbm6_evidence.py --blender /path/to/blender --dense --output build/visual_validation/BBM-6/full-chain-candidate-03

Only publish verified exact full source+evidence tree and mark general PASS after all gates. BBM-7–8 remain NOT STARTED. No main merge, deploy, source GLB mutation, constraint widening or usage-limit claim.
