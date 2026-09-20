"""Pas de Run — Phase 10.6.5 canonical foundation-pose solver.

Produces canonical body-space pose states from semantic intent, canonical
segment lengths, and Phase 10.6.3 constraints. It never reads Phase 10.6.4
reference fixtures and never touches the render rig.
"""

from __future__ import annotations

import copy
import math

from anatomical_constraints import evaluate_dof
from ballet_pose_validators import validate_pose


class PoseSolveRejected(RuntimeError):
    pass


def _v(values) -> list[float]:
    return [float(value) for value in values]


def _add(a, b):
    return [a[i] + b[i] for i in range(3)]


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _scale(a, amount):
    return [value * float(amount) for value in a]


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _length(a):
    return math.sqrt(_dot(a, a))


def _normalize(a):
    size = _length(a)
    if size <= 1e-12:
        raise PoseSolveRejected("Degenerate canonical direction.")
    return _scale(a, 1.0 / size)


def _project_orthogonal(value, normal):
    normal = _normalize(normal)
    return _sub(value, _scale(normal, _dot(value, normal)))


def _body_point(left: float, up: float, front: float) -> dict:
    return {"left": float(left), "up": float(up), "front": float(front)}


def _point_vec(point: dict) -> list[float]:
    return [float(point["left"]), float(point["up"]), float(point["front"])]


def _average(value_a: float, value_b: float) -> float:
    return (float(value_a) + float(value_b)) * 0.5


def _canonical_dimensions(canonical_profile: dict) -> dict:
    bones = canonical_profile["canonical_bones"]

    left_shoulder = bones["left_upper_arm"]["head_body"]
    right_shoulder = bones["right_upper_arm"]["head_body"]
    shoulder_half_width = _average(
        abs(float(left_shoulder["left"])),
        abs(float(right_shoulder["left"])),
    )
    shoulder_up = _average(left_shoulder["up"], right_shoulder["up"])
    shoulder_front = _average(left_shoulder["front"], right_shoulder["front"])

    upper_arm = _average(
        bones["left_upper_arm"]["length"],
        bones["right_upper_arm"]["length"],
    )
    forearm = _average(
        bones["left_forearm"]["length"],
        bones["right_forearm"]["length"],
    )
    hand = _average(
        bones["left_hand"]["length"],
        bones["right_hand"]["length"],
    )
    middle = _average(
        bones["left_middle"]["length"],
        bones["right_middle"]["length"],
    )
    hand_middle_chain = hand + middle
    foot = _average(
        float(bones["left_foot"]["length"]) + float(bones["left_toes"]["length"]),
        float(bones["right_foot"]["length"]) + float(bones["right_toes"]["length"]),
    )
    leg_chain = (
        float(bones["left_thigh"]["length"])
        + float(bones["left_shin"]["length"])
        + float(bones["left_foot"]["length"])
        + float(bones["right_thigh"]["length"])
        + float(bones["right_shin"]["length"])
        + float(bones["right_foot"]["length"])
    ) / 2.0

    head_up = float(bones["head"]["head_body"]["up"])
    left_foot_up = float(bones["left_foot"]["head_body"]["up"])
    right_foot_up = float(bones["right_foot"]["head_body"]["up"])
    floor_up = min(left_foot_up, right_foot_up)
    body_height = max(head_up - floor_up, upper_arm + forearm)

    values = {
        "shoulder_half_width": shoulder_half_width,
        "shoulder_up": shoulder_up,
        "shoulder_front": shoulder_front,
        "upper_arm": upper_arm,
        "forearm": forearm,
        "hand": hand,
        "middle": middle,
        "hand_middle_chain": hand_middle_chain,
        "foot": foot,
        "leg_chain": leg_chain,
        "body_height": body_height,
    }
    for name, value in values.items():
        if value <= 1e-6 and name != "shoulder_front":
            raise PoseSolveRejected(f"Invalid canonical dimension {name}={value}.")
    return values


def _desired_wrist_distance(
    upper_arm: float,
    forearm: float,
    elbow_angle_deg: float,
) -> float:
    theta = math.radians(float(elbow_angle_deg))
    return math.sqrt(
        upper_arm * upper_arm
        + forearm * forearm
        - 2.0 * upper_arm * forearm * math.cos(theta)
    )


def _wrist_constraints(
    pose_name: str,
    side: str,
    shoulder: list[float],
    grammar: dict,
) -> dict:
    constraints = {
        "minimum_front": None,
        "maximum_up": None,
        "minimum_up": None,
    }
    wrist_name = f"{side}_wrist"

    for check in grammar["poses"][pose_name]["checks"]:
        kind = check["type"]

        if kind == "anterior_halfspace" and wrist_name in check["landmarks"]:
            minimum = float(check["min_front"])
            current = constraints["minimum_front"]
            constraints["minimum_front"] = (
                minimum if current is None else max(current, minimum)
            )

        if kind == "wrist_below_shoulder":
            shoulder_name = check[f"{side}_shoulder"]
            if shoulder_name == f"{side}_shoulder":
                minimum_drop = float(check["min_drop"])
                maximum_drop = float(check["max_drop"])
                constraints["maximum_up"] = (
                    float(shoulder[1]) - minimum_drop
                )
                constraints["minimum_up"] = (
                    float(shoulder[1]) - maximum_drop
                )

    return constraints


def _wrist_satisfies_constraints(
    wrist: list[float],
    constraints: dict,
) -> bool:
    minimum_front = constraints["minimum_front"]
    if minimum_front is not None and float(wrist[2]) < minimum_front - 1e-9:
        return False

    maximum_up = constraints["maximum_up"]
    if maximum_up is not None and float(wrist[1]) > maximum_up + 1e-9:
        return False

    minimum_up = constraints["minimum_up"]
    if minimum_up is not None and float(wrist[1]) < minimum_up - 1e-9:
        return False

    return True


def _candidate_unit_directions(
    preferred: list[float],
    sample_count: int = 2048,
) -> list[list[float]]:
    preferred = _normalize(preferred)
    candidates = [preferred]

    # Deterministic Fibonacci sphere. Sort by angular similarity so semantic
    # intent remains the preference while grammar decides feasibility.
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    sampled = []
    for index in range(sample_count):
        z = 1.0 - 2.0 * ((index + 0.5) / sample_count)
        radius = math.sqrt(max(0.0, 1.0 - z * z))
        phi = index * golden_angle
        direction = [
            radius * math.cos(phi),
            z,
            radius * math.sin(phi),
        ]
        sampled.append((_dot(direction, preferred), direction))

    sampled.sort(key=lambda item: item[0], reverse=True)
    candidates.extend(direction for _, direction in sampled)
    return candidates


def _arm_elbow_constraints(
    pose_name: str,
    side: str,
    shoulder: list[float],
    wrist: list[float],
    grammar: dict,
) -> dict:
    sign = 1.0 if side == "left" else -1.0
    constraints = {
        "side_sign": sign,
        "minimum_front": None,
        "minimum_abs_left": None,
        "maximum_abs_left": None,
        "maximum_up": None,
        "minimum_up": None,
    }

    for check in grammar["poses"][pose_name]["checks"]:
        kind = check["type"]
        elbow_name = f"{side}_elbow"

        if kind == "anterior_halfspace" and elbow_name in check["landmarks"]:
            minimum = float(check["min_front"])
            current = constraints["minimum_front"]
            constraints["minimum_front"] = (
                minimum if current is None else max(current, minimum)
            )

        if kind == "axis_order" and check.get("axis") == "abs_left":
            margin = float(check["margin"])
            relation = check["relation"]
            wrist_abs = abs(float(wrist[0]))
            if relation == "elbow_gt_wrist":
                constraints["minimum_abs_left"] = wrist_abs + margin
            elif relation == "wrist_gt_elbow":
                constraints["maximum_abs_left"] = max(0.0, wrist_abs - margin)

        if (
            kind == "axis_order"
            and check.get("axis") == "up"
            and check.get("relation") == "shoulder_gt_elbow_gt_wrist"
        ):
            margin = float(check["margin"])
            constraints["maximum_up"] = float(shoulder[1]) - margin
            constraints["minimum_up"] = float(wrist[1]) + margin

    return constraints


def _elbow_satisfies_constraints(
    elbow: list[float],
    constraints: dict,
) -> bool:
    abs_left = abs(float(elbow[0]))
    front = float(elbow[2])
    up = float(elbow[1])

    minimum_front = constraints["minimum_front"]
    if minimum_front is not None and front < minimum_front - 1e-9:
        return False

    minimum_abs_left = constraints["minimum_abs_left"]
    if minimum_abs_left is not None and abs_left < minimum_abs_left - 1e-9:
        return False

    maximum_abs_left = constraints["maximum_abs_left"]
    if maximum_abs_left is not None and abs_left > maximum_abs_left + 1e-9:
        return False

    maximum_up = constraints["maximum_up"]
    if maximum_up is not None and up > maximum_up + 1e-9:
        return False

    minimum_up = constraints["minimum_up"]
    if minimum_up is not None and up < minimum_up - 1e-9:
        return False

    sign = float(constraints["side_sign"])
    if sign * float(elbow[0]) < -1e-9:
        return False

    return True


def _two_bone_elbow(
    shoulder: list[float],
    wrist: list[float],
    upper_arm: float,
    forearm: float,
    pole: list[float],
    constraints: dict,
) -> list[float]:
    delta = _sub(wrist, shoulder)
    distance = _length(delta)
    minimum = abs(upper_arm - forearm) + 1e-8
    maximum = upper_arm + forearm - 1e-8
    if not minimum < distance < maximum:
        raise PoseSolveRejected(
            f"Arm target unreachable: d={distance}, range=({minimum},{maximum})."
        )

    along = _scale(delta, 1.0 / distance)
    x = (
        upper_arm * upper_arm
        - forearm * forearm
        + distance * distance
    ) / (2.0 * distance)
    height_sq = max(0.0, upper_arm * upper_arm - x * x)
    height = math.sqrt(height_sq)
    center = _add(shoulder, _scale(along, x))

    preferred = _normalize(_project_orthogonal(pole, along))
    tangent = _normalize(_cross(along, preferred))

    # Deterministic feasibility search around the exact two-bone elbow circle.
    # This is not coefficient tuning: segment lengths stay exact and grammar
    # inequalities decide which geometric solutions are admissible.
    angles_deg = [0.0]
    for step in range(1, 721):
        angle = step * 0.25
        angles_deg.extend((angle, -angle))

    for angle_deg in angles_deg:
        angle = math.radians(angle_deg)
        direction = _add(
            _scale(preferred, math.cos(angle)),
            _scale(tangent, math.sin(angle)),
        )
        elbow = _add(center, _scale(direction, height))
        if _elbow_satisfies_constraints(elbow, constraints):
            return elbow

    raise PoseSolveRejected(
        "No exact two-bone elbow solution satisfies pose geometry: "
        f"{constraints}"
    )


def _fingertip_spacing_contract(
    intent: dict,
    dimensions: dict,
) -> dict | None:
    spec = intent.get("fingertip_gap_chain_fraction")
    if spec is None:
        return None

    minimum_fraction = float(spec["min"])
    maximum_fraction = float(spec["max"])
    if not 0.0 < minimum_fraction < maximum_fraction:
        raise PoseSolveRejected(
            "Fingertip gap fractions must satisfy 0 < min < max."
        )

    scale_length = float(dimensions["hand_middle_chain"])
    return {
        "scale_basis": "average_hand_plus_middle_chain_length",
        "scale_length": scale_length,
        "minimum_fraction": minimum_fraction,
        "maximum_fraction": maximum_fraction,
        "minimum_gap": scale_length * minimum_fraction,
        "maximum_gap": scale_length * maximum_fraction,
    }


def _arm_geometry(
    pose_name: str,
    intent: dict,
    grammar: dict,
    dimensions: dict,
) -> dict:
    upper_arm = dimensions["upper_arm"]
    forearm = dimensions["forearm"]
    hand_length = dimensions["hand"]
    fingertip_contract = _fingertip_spacing_contract(
        intent,
        dimensions,
    )
    shoulder_half = dimensions["shoulder_half_width"]
    shoulder_up = dimensions["shoulder_up"]
    shoulder_front = dimensions["shoulder_front"]
    wrist_distance = _desired_wrist_distance(
        upper_arm,
        forearm,
        intent["elbow_angle_deg"],
    )

    anterior_checks = [
        check
        for check in grammar["poses"][pose_name]["checks"]
        if check["type"] == "anterior_halfspace"
    ]
    wrist_front_min = max(
        (
            float(check["min_front"])
            for check in anterior_checks
            if "left_wrist" in check["landmarks"]
        ),
        default=0.0,
    )
    elbow_front_min = max(
        (
            float(check["min_front"])
            for check in anterior_checks
            if "left_elbow" in check["landmarks"]
        ),
        default=0.0,
    )

    landmarks = {}
    for side, sign in (("left", 1.0), ("right", -1.0)):
        shoulder = [
            sign * shoulder_half,
            shoulder_up,
            shoulder_front,
        ]

        if side == "right":
            for joint in (
                "shoulder",
                "elbow",
                "wrist",
                "hand",
            ):
                source = landmarks[f"left_{joint}"]
                landmarks[f"right_{joint}"] = _body_point(
                    -float(source["left"]),
                    float(source["up"]),
                    float(source["front"]),
                )
            continue

        raw_direction = intent["wrist_direction"]
        lateral_key = "inward" if "inward" in raw_direction else "outward"
        lateral_sign = -sign if lateral_key == "inward" else sign
        preferred_direction = _normalize(
            [
                lateral_sign * float(raw_direction[lateral_key]),
                -float(raw_direction["down"]),
                float(raw_direction["front"]),
            ]
        )

        pole_spec = intent["elbow_pole"]
        pole = [
            sign * float(pole_spec["outward"]),
            -float(pole_spec["down"]),
            float(pole_spec["front"]),
        ]

        hand_spec = intent["hand_direction"]
        hand_lateral_key = (
            "inward" if "inward" in hand_spec else "outward"
        )
        hand_lateral_sign = (
            -sign if hand_lateral_key == "inward" else sign
        )
        hand_direction = _normalize(
            [
                hand_lateral_sign * float(hand_spec[hand_lateral_key]),
                -float(hand_spec["down"]),
                float(hand_spec["front"]),
            ]
        )
        centerline_policy = intent.get("centerline_hand_policy")
        if centerline_policy not in (
            None,
            "TOUCH_NOT_CROSS",
            "FINGERTIP_NEAR_TOUCH_NOT_CROSS",
        ):
            raise PoseSolveRejected(
                f"{pose_name}: unknown centerline hand policy "
                f"{centerline_policy!r}."
            )

        wrist_constraints = _wrist_constraints(
            pose_name,
            side,
            shoulder,
            grammar,
        )
        if wrist_constraints["minimum_front"] is None:
            wrist_constraints["minimum_front"] = wrist_front_min

        wrist = None
        elbow = None
        hand = None
        for direction in _candidate_unit_directions(preferred_direction):
            candidate_wrist = _add(
                shoulder,
                _scale(direction, wrist_distance),
            )
            if not _wrist_satisfies_constraints(
                candidate_wrist,
                wrist_constraints,
            ):
                continue

            candidate_hand = _add(
                candidate_wrist,
                _scale(hand_direction, hand_length),
            )
            if centerline_policy in (
                "TOUCH_NOT_CROSS",
                "FINGERTIP_NEAR_TOUCH_NOT_CROSS",
            ):
                if sign * float(candidate_wrist[0]) < -1e-9:
                    continue
                if sign * float(candidate_hand[0]) < -1e-9:
                    continue

            elbow_constraints = _arm_elbow_constraints(
                pose_name,
                side,
                shoulder,
                candidate_wrist,
                grammar,
            )
            if elbow_constraints["minimum_front"] is None:
                elbow_constraints["minimum_front"] = elbow_front_min

            try:
                candidate_elbow = _two_bone_elbow(
                    shoulder,
                    candidate_wrist,
                    upper_arm,
                    forearm,
                    pole,
                    elbow_constraints,
                )
            except PoseSolveRejected:
                continue

            wrist = candidate_wrist
            elbow = candidate_elbow
            hand = candidate_hand
            break

        if wrist is None or elbow is None or hand is None:
            raise PoseSolveRejected(
                f"{pose_name}/{side}: no wrist/elbow/hand solution "
                "satisfies grammar and centerline policy."
            )

        landmarks[f"{side}_shoulder"] = _body_point(*shoulder)
        landmarks[f"{side}_elbow"] = _body_point(*elbow)
        landmarks[f"{side}_wrist"] = _body_point(*wrist)
        landmarks[f"{side}_hand"] = _body_point(*hand)

    return landmarks


def _joint_dofs_for_arm_pose(intent: dict) -> dict:
    result = {}
    for side in ("left", "right"):
        result[f"{side}_upper_arm"] = copy.deepcopy(
            intent["joint_dofs"]["upper_arm"]
        )
        result[f"{side}_forearm"] = copy.deepcopy(
            intent["joint_dofs"]["forearm"]
        )
        result[f"{side}_hand"] = copy.deepcopy(
            intent["joint_dofs"]["hand"]
        )
    return result


def _turnout(intent: dict) -> dict:
    request = {
        "hip_external_rotation_deg": float(
            intent["hip_external_rotation_deg"]
        ),
        "knee_external_rotation_deg": float(
            intent["knee_external_rotation_deg"]
        ),
        "knee_flexion_deg": float(intent["knee_flexion_deg"]),
        "independent_foot_yaw_deg": 0.0,
    }
    return {"left": copy.deepcopy(request), "right": copy.deepcopy(request)}


def _lower_joint_dofs(intent: dict) -> dict:
    result = {}
    mapping = (
        ("thigh", "thigh"),
        ("shin", "shin"),
        ("foot", "foot"),
        ("toes", "toes"),
    )
    for side in ("left", "right"):
        for source_name, suffix in mapping:
            result[f"{side}_{suffix}"] = copy.deepcopy(
                intent["joint_dofs"][source_name]
            )
    return result


def _support_polygon(half_width: float, half_depth: float) -> list[dict]:
    return [
        {"left": -half_width, "front": -half_depth},
        {"left": half_width, "front": -half_depth},
        {"left": half_width, "front": half_depth},
        {"left": -half_width, "front": half_depth},
    ]


def _solve_fifth(intent: dict, dimensions: dict) -> dict:
    foot = dimensions["foot"]
    cross = max(0.03, foot * float(intent["foot_cross_fraction"]))
    half_width = max(
        cross,
        foot * float(intent["support_half_width_fraction"]),
    )
    half_depth = max(
        cross,
        foot * float(intent["support_half_depth_fraction"]),
    )
    return {
        "pose": "fifth",
        "landmarks": {
            "left_heel": _body_point(-cross, 0.0, cross),
            "left_toe": _body_point(cross, 0.0, -cross),
            "right_heel": _body_point(cross, 0.0, -cross),
            "right_toe": _body_point(-cross, 0.0, cross),
        },
        "contacts": {"left": "FULL_FOOT", "right": "FULL_FOOT"},
        "turnout": _turnout(intent),
        "com": {"left": 0.0, "front": 0.0},
        "support_polygon": _support_polygon(half_width, half_depth),
        "joint_dofs": _lower_joint_dofs(intent),
    }


def _solve_plie(intent: dict, dimensions: dict) -> dict:
    foot = dimensions["foot"]
    leg_chain = dimensions["leg_chain"]
    descent = leg_chain * float(
        intent["pelvis_descent_leg_fraction"]
    )
    descent = min(
        max(descent, leg_chain * 0.04),
        leg_chain * 0.30,
    )
    half_width = max(
        0.12,
        foot * float(intent["support_half_width_fraction"]),
    )
    half_depth = max(
        0.10,
        foot * float(intent["support_half_depth_fraction"]),
    )
    error = float(intent["knee_second_toe_error_deg"])
    return {
        "pose": "plie",
        "contacts": {"left": "FULL_FOOT", "right": "FULL_FOOT"},
        "turnout": _turnout(intent),
        "knee_second_toe_error_deg": {
            "left": error,
            "right": error,
        },
        "scalars": {
            "pelvis_descent": descent,
            "trunk_tilt_deg": float(intent["trunk_tilt_deg"]),
        },
        "com": {"left": 0.0, "front": 0.0},
        "support_polygon": _support_polygon(half_width, half_depth),
        "joint_dofs": _lower_joint_dofs(intent),
    }


def _solve_releve(intent: dict, dimensions: dict) -> dict:
    foot = dimensions["foot"]
    heel_height = foot * float(intent["heel_height_foot_fraction"])
    heel_height = min(max(heel_height, 0.06), 0.30)
    half_width = max(
        0.08,
        foot * float(intent["support_half_width_fraction"]),
    )
    half_depth = max(
        0.06,
        foot * float(intent["support_half_depth_fraction"]),
    )
    com_front = min(
        half_depth * 0.5,
        foot * float(intent["com_front_fraction"]),
    )
    return {
        "pose": "releve",
        "contacts": {"left": "FOREFOOT", "right": "FOREFOOT"},
        "turnout": _turnout(intent),
        "scalars": {
            "left_heel_height": heel_height,
            "right_heel_height": heel_height,
        },
        "com": {"left": 0.0, "front": com_front},
        "support_polygon": _support_polygon(half_width, half_depth),
        "joint_dofs": _lower_joint_dofs(intent),
    }


def _check_preferred_joint_envelope(
    state: dict,
    constraint_profile: dict,
) -> list[str]:
    violations = []
    bone_constraints = constraint_profile["bone_constraints"]
    for bone_name, dofs in state.get("joint_dofs", {}).items():
        if bone_name not in bone_constraints:
            violations.append(f"unknown_bone:{bone_name}")
            continue
        joint_class = bone_constraints[bone_name]["joint_class"]
        for dof_name, value in dofs.items():
            result = evaluate_dof(
                constraint_profile,
                joint_class,
                dof_name,
                value,
            )
            if result.status != "PASS":
                violations.append(
                    f"{bone_name}.{dof_name}:{result.status}:{value}"
                )
    return violations


def _arm_length_evidence(state: dict, dimensions: dict) -> dict:
    evidence = {}
    for side in ("left", "right"):
        shoulder = _point_vec(state["landmarks"][f"{side}_shoulder"])
        elbow = _point_vec(state["landmarks"][f"{side}_elbow"])
        wrist = _point_vec(state["landmarks"][f"{side}_wrist"])
        upper = _length(_sub(elbow, shoulder))
        forearm = _length(_sub(wrist, elbow))
        evidence[side] = {
            "upper_arm_error": abs(upper - dimensions["upper_arm"]),
            "forearm_error": abs(forearm - dimensions["forearm"]),
        }
    return evidence


def solve_pose(
    pose_name: str,
    intent_spec: dict,
    grammar_profile: dict,
    canonical_profile: dict,
    constraint_profile: dict,
) -> dict:
    if pose_name not in intent_spec["poses"]:
        raise PoseSolveRejected(f"Unknown pose intent: {pose_name}")
    if pose_name not in grammar_profile["poses"]:
        raise PoseSolveRejected(f"Pose absent from grammar: {pose_name}")

    dimensions = _canonical_dimensions(canonical_profile)
    intent = intent_spec["poses"][pose_name]
    kind = intent["kind"]

    if kind == "symmetric_arm_chain":
        state = {
            "pose": pose_name,
            "landmarks": _arm_geometry(
                pose_name,
                intent,
                grammar_profile,
                dimensions,
            ),
            "joint_dofs": _joint_dofs_for_arm_pose(intent),
        }
        fingertip_contract = _fingertip_spacing_contract(
            intent,
            dimensions,
        )
        if fingertip_contract is not None:
            state["fingertip_spacing_contract"] = fingertip_contract
    elif pose_name == "fifth":
        state = _solve_fifth(intent, dimensions)
    elif pose_name == "plie":
        state = _solve_plie(intent, dimensions)
    elif pose_name == "releve":
        state = _solve_releve(intent, dimensions)
    else:
        raise PoseSolveRejected(
            f"No solver implementation for {pose_name}/{kind}."
        )

    preferred_violations = _check_preferred_joint_envelope(
        state,
        constraint_profile,
    )
    if preferred_violations:
        raise PoseSolveRejected(
            "Foundation pose left preferred joint envelope: "
            + "; ".join(preferred_violations)
        )

    validation = validate_pose(
        state,
        grammar_profile["poses"][pose_name],
        constraint_profile,
        canonical_profile,
    )
    if validation["status"] != "PASS":
        raise PoseSolveRejected(
            f"{pose_name} failed geometric gate: {validation}"
        )

    evidence = {
        "preferred_joint_envelope": "PASS",
        "geometry_gate": "PASS",
    }
    if kind == "symmetric_arm_chain":
        arm_lengths = _arm_length_evidence(state, dimensions)
        maximum_error = max(
            item
            for side in arm_lengths.values()
            for item in side.values()
        )
        if maximum_error > 1e-7:
            raise PoseSolveRejected(
                f"{pose_name}: arm segment length error {maximum_error}."
            )
        evidence["arm_segment_lengths"] = arm_lengths
        if "fingertip_spacing_contract" in state:
            evidence["fingertip_spacing"] = {
                "status": "DEFERRED_TO_CALIBRATED_RETARGET",
                "authority": "Phase 10.6.6 calibrated Hand->Middle rest/bind geometry",
            }

    return {
        "pose": pose_name,
        "state": state,
        "validation": validation,
        "evidence": evidence,
    }


def apply_rejection_probe(
    solution: dict,
    probe: dict,
) -> dict:
    state = copy.deepcopy(solution["state"])
    mutation = probe["mutation"]

    if mutation == "mirror_arm_front_to_posterior":
        for name, point in state["landmarks"].items():
            if any(token in name for token in ("elbow", "wrist", "hand")):
                point["front"] = -abs(float(point["front"])) - 0.05
    elif mutation == "lock_arms_to_shoulder_height":
        for side in ("left", "right"):
            shoulder_up = state["landmarks"][f"{side}_shoulder"]["up"]
            for joint in ("elbow", "wrist", "hand"):
                state["landmarks"][f"{side}_{joint}"]["up"] = shoulder_up
    elif mutation == "inject_left_foot_yaw":
        state["turnout"]["left"]["independent_foot_yaw_deg"] = float(
            probe["value"]
        )
    elif mutation == "move_com_outside_support":
        max_left = max(
            float(point["left"])
            for point in state["support_polygon"]
        )
        state["com"]["left"] = max_left + 1.0
    else:
        raise PoseSolveRejected(f"Unknown rejection probe mutation: {mutation}")

    return state


def evaluate_rejection_probe(
    probe: dict,
    intent_spec: dict,
    grammar_profile: dict,
    canonical_profile: dict,
    constraint_profile: dict,
) -> dict:
    base_pose = probe["base_pose"]
    solution = solve_pose(
        base_pose,
        intent_spec,
        grammar_profile,
        canonical_profile,
        constraint_profile,
    )
    mutated = apply_rejection_probe(solution, probe)
    validation = validate_pose(
        mutated,
        grammar_profile["poses"][base_pose],
        constraint_profile,
        canonical_profile,
    )
    required = probe["must_fail_validator"]
    rejected = (
        validation["status"] == "FAIL"
        and required in validation["failed_validators"]
    )
    return {
        "status": "REJECTED" if rejected else "NOT_REJECTED",
        "base_pose": base_pose,
        "required_failed_validator": required,
        "validation": validation,
    }
