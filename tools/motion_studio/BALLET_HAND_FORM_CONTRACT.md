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

## Rig verification and implementation status

The final Rig has been verified to contain independent Thumb, Index, Middle, Ring and Pinky chains on both hands, with three bones per finger. The historical Ring_L/R source naming inversion was repaired in the canonical GLB and validated through export round-trip plus Phase 10.6 regeneration.

Canonical finger mapping:
- `tools/motion_studio/low_poly_girl_finger_mapping_v0_1.json`
- repaired source GLB SHA-256: `ae03b92e46f71db3630872f9ba212e6700561164c71ca1f6576c58996ce7bea8`

Implementation policy:
1. Finger-aware tools must use the canonical finger mapping rather than infer finger identity from traversal order.
2. Wrist continuity is a separate acceptance requirement from finger curl/spread.
3. Hand-roll alone cannot satisfy this contract.
4. The provisional First Position arm scaffold is geometry scaffolding only until a finger-aware candidate passes visual review.

## Acceptance gate

A hand pose is not accepted merely because:
- hand silhouettes do not overlap,
- wrist/hand bone endpoints hit geometric targets,
- a hand-roll angle looks less bad.

Acceptance requires visual continuity through forearm→wrist→hand, inward-facing first-position fingertips, relaxed finger spacing, and the finger hierarchy above. Teacher review may remain deferred, but unresolved violations must stay explicit.
