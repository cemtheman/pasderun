# ChatGPT Work Prompt — Pas de Run / Ballet Body Model v1

Work autonomously on repository `cemtheman/pasderun` following the repository journal and roadmap.

## Read first
Before editing anything, locate and read:
- `docs/PASDERUN_PROJECT_JOURNAL.md`
- `docs/BALLET_BODY_MODEL_V1_ROADMAP.md`
- all existing `assets/ballet_motion/*` contracts relevant to the active milestone;
- relevant `tools/ballet_motion/*` and `tools/blender/*` tests/runners.

Treat the journal and roadmap as the controlling methodology.

## Current baseline
Safe main baseline at handoff:
`080d42cb076a0efcc4902bbef7d9e42aae5550e3`

Do not assume the working branch still matches that SHA. Verify first.

## Mission
Execute the Ballet Body Model v1 roadmap in order, beginning with BBM-0 and BBM-1. Continue through later milestones when each gate is satisfied and there is no human-review stop condition.

The immediate proof target is the already accepted Motion Studio upper-body phrase:
**preparation -> opening -> second position**.

The new architecture must reproduce or improve that accepted visual result rather than replace it with a theoretically cleaner but visibly worse motion.

## Engineering rules
- Do not rewrite the existing ballet-motion stack if an extension is sufficient.
- Keep changes milestone-scoped and reviewable.
- Never mutate the source GLB merely to make a test pass.
- Never weaken a hard constraint, geometric test, or visual gate silently.
- Do not alter unrelated gameplay/topology/timing.
- Preserve a rollback path.
- Add tests for new behavior.
- Run focused tests after each coherent change, then the relevant broader suite.
- Record every meaningful decision in the journal.

## Required visual workflow
You are responsible for visual engineering review as well as code.

For every candidate that changes visible pose or motion:
1. Generate deterministic evidence with fixed camera, framing, lighting and scale.
2. Produce FRONT / THREE_QUARTER / SIDE views for static poses.
3. For motion, also generate deterministic sampled-frame strips and, where practical, a short preview.
4. Compare candidate with the locked baseline.
5. Inspect the actual rendered images yourself.
6. Record an explicit provisional verdict:
   - `AI_VISUAL_PASS`
   - `AI_VISUAL_REVISE`
7. If REVISE, state the visible defect precisely, identify the smallest likely cause, change only that layer, rerun tests and render again.
8. Do not use code/metrics alone as proof of visual correctness.

Evaluate at least:
- shoulder elevation and neck freedom;
- elbow roundness/locking;
- wrist and hand continuity;
- palm/forearm orientation;
- hand/finger silhouette;
- epaulement/head/gaze relationship;
- turnout origin and compensation;
- knee-toe alignment;
- foot/ankle organization;
- pelvis/trunk compensation;
- support and weight transfer;
- timing/phase relationships.

## Acceptance hierarchy
A candidate can advance only when:
1. automated/geometric gate passes;
2. relevant tests pass;
3. AI visual review passes.

AI visual PASS is not final artistic acceptance. At the roadmap's human checkpoints, stop and present the smallest useful evidence pack to the user for `HUMAN_ACCEPT` or `REVISE`.

## BBM-0
Audit and reproduce the current baseline. Do not edit implementation until you know:
- current SHA/branch;
- current relevant tests;
- current contracts;
- whether Blender visual evidence can be regenerated;
- exact baseline evidence paths.

If baseline evidence cannot be generated because of environment/tooling, repair the evidence path if safe; otherwise record the blocker and stop.

## BBM-1
Implement the upper-body proof:
- formalize scapular/clavicular participation;
- shoulder/elbow/forearm/wrist/hand coordination;
- joint phase offsets;
- head/epaulement/gaze coordination;
- preserve accepted arm v0.6 visual character.

Use minimal changes and avoid unrelated lower-body work except what is necessary to preserve the reference pose.

When BBM-1 reaches:
- tests PASS,
- geometric gate PASS,
- AI_VISUAL_PASS,

stop for human review with:
- commit SHA;
- changed files;
- test summary;
- baseline/candidate contact sheets;
- motion frame strip/preview;
- brief statement of what visibly improved and any remaining caveat.

After human acceptance, continue to BBM-2 and onward under the same methodology.

## Reporting
Keep the journal current while working. Do not wait until the end.

At each milestone record:
- starting SHA;
- ending SHA;
- files changed;
- tests and results;
- visual artifacts;
- AI visual verdict;
- unresolved risks;
- next step.

Do not declare completion merely because code compiles. Completion requires evidence.
