# BBM-3 engineering visual review

**AI_VISUAL_PASS** for conservative foot semantics and pointe-ready preparation.

Compared all eighteen paired FRONT/3Q/SIDE cells and both enlarged foot-detail sheets. Flat contact remains stable; demi-pointe raises the heel about0.078 while keeping the toe platform organized; pointe-ready produces a visibly elongated foot line and about0.136 heel lift in an open symmetric preparation. Upright trunk/available neck space and accepted BBM-1 carriage remain. The source's low-poly footwear/heel silhouette remains visible; this is not a barefoot anatomical or full en-pointe demonstration.

Important frame correction: locked BBM-0 flat contact identifies32.377°left /32.392°right canonical ankle neutral offsets. Anatomical preferred50° / hard60° limits are unchanged and checked relative to this source-bound neutral. Encoded canonical angles include the offset; they must not be mistaken for anatomical ROM. Boundary tests still reject51°preferred and61°hard requests. No source GLB or legacy production constraint changed.

All implemented final gates PASS: unchanged deformed-mesh contact, <=6°preferred toe-ray tracking (max1.80°), preferred anatomical foot/MTP angles, local rotation orthogonality/determinant, source bone lengths, independent foot/toe world matrix reconstruction <=1e-5 and existing wrist continuity. Parent matrix rounding diagnosed numerically; inverse relation plus proper local SO(3) rotation satisfies both local/world gates, without widening thresholds.

358 tests PASS. Pelvis-to-support is only a limited proxy; BBM-4 will assess a declared whole-body COM proxy and support polygon. Arch/hindfoot without separate bones stay semantic. Closed-first pointe-ready failed tracking and remains REVISE; accepted pointe-ready uses an open symmetric preparation. No gameplay integration yet.

Reproduce: `python3 tools/visual_validation/run_bbm3_evidence.py --blender <blender>`.
