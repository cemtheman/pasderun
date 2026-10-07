# BBM-6 source-only recovery snapshot

This isolated branch contains four sources reconstructed from the authorized tool inputs after the local execution transport closed. They are intended to reproduce the last local jump run, but exact equality to inaccessible local source hashes is NOT VERIFIED. No BBM-6 generated report, PNG or GIF has been published here, and this branch is NOT an accepted milestone checkpoint. Do not merge it into the active checkpoint merely because local MACHINE_PASS was observed.

Base: complete BBM-5 plus interruption handoff. Existing source GLB, BodyRuntime and prior evidence are unchanged. Inspect the Morning Handoff and project journal for local measurements, reviewed paths and outstanding checks.

After restoring execution, prefer the original owned local BBM-6 files/evidence if available and validate their source SHA bindings. If unavailable, run these reconstructed sources through all focused tests, syntax/diff checks and the deterministic Blender harness:
```sh
python3 -m unittest discover -s tools/ballet_motion -p 'test*.py'
python3 -m unittest discover -s tools/blender -p 'test*.py'
python3 -m unittest discover -s tools/motion_studio -p 'test*.py'
python3 tools/visual_validation/run_bbm6_evidence.py --blender /path/to/blender
```

The local Blender4.0.2 wrapper additionally used the source installation scripts/datafiles and Python/Pillow paths documented in prior runtime setup. Restore the runtime if scratch was replaced. Report must be machine PASS, all raw/composite/GIF files fully decoded, all source hashes bound, and baseline/candidate primary/boundary strips plus all49 samples ACTUALLY reviewed before AI_VISUAL_PASS and milestone promotion. Current generator intentionally writes NOT_REVIEWED.

No quota exhaustion, human aesthetic preference or source mesh change is asserted. Interruption is execution/evidence infrastructure only.
