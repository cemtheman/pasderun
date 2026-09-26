# Ballet Hand Form Contract v0.1

Status: USER-SPECIFIED / NOT YET IMPLEMENTED

This contract records the user's required ballet hand presentation for Motion Studio. It is a production requirement, not a claim of teacher approval.

## Finger presentation

- Thumb: softly drawn toward the palm; not fully tucked. It should aim gently toward the second joint of the middle finger.
- Middle finger: slightly lower and more inward than the other fingers. Keep a small imaginary droplet-shaped space between thumb and middle finger.
- Index finger: slightly higher and more extended than the other fingers; it visually continues the hand line.
- Ring and pinky: follow the middle finger with a natural graduated curve.

## Global hand shape

- Natural curve: the hand should read as if lightly holding a small oval object such as an apple or egg.
- Wrist continuity: the wrist must not form a hard bend. Energy/line should continue from forearm through wrist to fingertips without an obvious break.
- Relaxed separation: fingers must not be glued together and must not look limp.
- Avoid spoon-hand: fingers straight, flat and pressed together.
- Avoid claw-hand: excessive flexion or gripping.

## First-position specific visual rule

- Fingertips should point toward each other.
- Hands should close the arm oval rather than sit flat against the abdomen.
- Palm/hand plane should not face the audience too directly.
- Wrist/hand line should remain a natural continuation of the forearm.

## Current rig limitation / open verification

The current canonical Motion Studio rig profile exposes Hand_L/Hand_R and Middle_L/Middle_R as canonical hand landmarks. Thumb, index, ring and pinky are not currently canonicalized.

Before implementation:
1. Inspect the actual final Rig bone inventory for additional finger bones.
2. If individual finger bones exist, add an explicit finger calibration/mapping layer and implement this contract per finger.
3. If they do not exist, do not pretend hand-roll alone satisfies this contract. Evaluate a hand-specific rig extension, shape keys, or a revised character rig.
4. Preserve the current provisional first-position waypoint only as geometry scaffolding; it is not an accepted ballet hand.

## Acceptance gate

A hand pose is not accepted merely because:
- hand silhouettes do not overlap,
- wrist/hand bone endpoints hit geometric targets,
- a hand-roll angle looks less bad.

Acceptance requires visual continuity through forearm→wrist→hand, inward-facing first-position fingertips, relaxed finger spacing, and the finger hierarchy above. Teacher review may remain deferred, but unresolved violations must stay explicit.
