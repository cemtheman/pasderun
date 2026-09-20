"""Phase 10.6.4 geometric ballet pose validators."""

from __future__ import annotations

import math

from anatomical_constraints import evaluate_dof, validate_turnout_request


def _point(state: dict, name: str) -> dict:
    try:
        return state["landmarks"][name]
    except KeyError as exc:
        raise ValueError(f"Missing landmark: {name}") from exc


def _distance_2d(a: dict, b: dict) -> float:
    return math.hypot(float(a["left"]) - float(b["left"]), float(a["front"]) - float(b["front"]))


def _angle_deg(a: dict, b: dict, c: dict) -> float:
    # Angle ABC in canonical LEFT/UP/FRONT body coordinates.
    ba = [float(a[k]) - float(b[k]) for k in ("left", "up", "front")]
    bc = [float(c[k]) - float(b[k]) for k in ("left", "up", "front")]
    dot = sum(ba[i] * bc[i] for i in range(3))
    la = math.sqrt(sum(value * value for value in ba))
    lc = math.sqrt(sum(value * value for value in bc))
    if la <= 1e-12 or lc <= 1e-12:
        raise ValueError("Degenerate angle landmark chain.")
    cosine = max(-1.0, min(1.0, dot / (la * lc)))
    return math.degrees(math.acos(cosine))


def _inside_convex_polygon(point: dict, polygon: list[dict]) -> bool:
    if len(polygon) < 3:
        raise ValueError("Support polygon needs at least three vertices.")
    px = float(point["left"])
    py = float(point["front"])
    sign = 0
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        ax, ay = float(start["left"]), float(start["front"])
        bx, by = float(end["left"]), float(end["front"])
        cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
        if abs(cross) <= 1e-10:
            continue
        current = 1 if cross > 0 else -1
        if sign == 0:
            sign = current
        elif current != sign:
            return False
    return True


def _fail(kind: str, detail: str) -> dict:
    return {"passed": False, "validator": kind, "detail": detail}


def _pass(kind: str) -> dict:
    return {"passed": True, "validator": kind}


def validate_check(
    state: dict,
    check: dict,
    constraint_profile: dict,
    canonical_profile: dict,
) -> dict:
    kind = check["type"]

    if kind == "anterior_halfspace":
        minimum = float(check["min_front"])
        for name in check["landmarks"]:
            front = float(_point(state, name)["front"])
            if front < minimum:
                return _fail(
                    kind,
                    f"{name}.front={front:.6f} < {minimum:.6f}",
                )
        return _pass(kind)

    if kind == "bilateral_mirror":
        tolerance = float(check["tolerance"])
        for left_name, right_name in check["pairs"]:
            left = _point(state, left_name)
            right = _point(state, right_name)
            errors = {
                "left_sum": abs(float(left["left"]) + float(right["left"])),
                "up": abs(float(left["up"]) - float(right["up"])),
                "front": abs(float(left["front"]) - float(right["front"])),
            }
            if max(errors.values()) > tolerance:
                return _fail(kind, f"{left_name}/{right_name}:{errors}")
        return _pass(kind)

    if kind == "axis_order":
        margin = float(check["margin"])
        if check["axis"] == "abs_left":
            left_elbow = abs(float(_point(state, check["left_elbow"])["left"]))
            left_wrist = abs(float(_point(state, check["left_wrist"])["left"]))
            right_elbow = abs(float(_point(state, check["right_elbow"])["left"]))
            right_wrist = abs(float(_point(state, check["right_wrist"])["left"]))
            relation = check["relation"]
            if relation == "elbow_gt_wrist":
                ok = left_elbow >= left_wrist + margin and right_elbow >= right_wrist + margin
            elif relation == "wrist_gt_elbow":
                ok = left_wrist >= left_elbow + margin and right_wrist >= right_elbow + margin
            else:
                raise ValueError(f"Unknown abs_left relation: {relation}")
            return _pass(kind) if ok else _fail(kind, relation)

        if check["axis"] == "up" and check["relation"] == "shoulder_gt_elbow_gt_wrist":
            for chain_name in ("left_chain", "right_chain"):
                shoulder, elbow, wrist = [_point(state, item) for item in check[chain_name]]
                if not (
                    float(shoulder["up"]) >= float(elbow["up"]) + margin
                    and float(elbow["up"]) >= float(wrist["up"]) + margin
                ):
                    return _fail(kind, chain_name)
            return _pass(kind)

        raise ValueError(f"Unknown axis_order contract: {check}")

    if kind == "elbow_angle_range":
        minimum = float(check["min_deg"])
        maximum = float(check["max_deg"])
        for side in ("left", "right"):
            a, b, c = [_point(state, item) for item in check[side]]
            angle = _angle_deg(a, b, c)
            if angle < minimum or angle > maximum:
                return _fail(kind, f"{side}={angle:.6f}")
        return _pass(kind)

    if kind == "wrist_below_shoulder":
        minimum = float(check["min_drop"])
        maximum = float(check["max_drop"])
        for side in ("left", "right"):
            shoulder = _point(state, check[f"{side}_shoulder"])
            wrist = _point(state, check[f"{side}_wrist"])
            drop = float(shoulder["up"]) - float(wrist["up"])
            if drop < minimum or drop > maximum:
                return _fail(kind, f"{side}_drop={drop:.6f}")
        return _pass(kind)

    if kind == "contact_mode":
        contacts = state.get("contacts", {})
        if contacts.get("left") != check["left"] or contacts.get("right") != check["right"]:
            return _fail(kind, f"contacts={contacts}")
        return _pass(kind)

    if kind == "fifth_closure":
        pairs = (
            (check["left_heel"], check["right_toe"]),
            (check["right_heel"], check["left_toe"]),
        )
        maximum = float(check["max_cross_endpoint_distance"])
        for a_name, b_name in pairs:
            distance = _distance_2d(_point(state, a_name), _point(state, b_name))
            if distance > maximum:
                return _fail(kind, f"{a_name}/{b_name}={distance:.6f}")
        return _pass(kind)

    if kind == "turnout_chain":
        for side in check["sides"]:
            request = state.get("turnout", {}).get(side)
            if request is None:
                return _fail(kind, f"missing turnout:{side}")
            result = validate_turnout_request(constraint_profile, **request)
            if result["status"] == "HARD_LIMIT":
                return _fail(kind, f"{side}:{result['violations']}")
        return _pass(kind)

    if kind == "knee_second_toe_tracking":
        errors = state.get("knee_second_toe_error_deg", {})
        hard = float(check["hard_error_deg"])
        preferred = float(check["preferred_error_deg"])
        soft = []
        for side in check["sides"]:
            if side not in errors:
                return _fail(kind, f"missing:{side}")
            value = abs(float(errors[side]))
            if value > hard:
                return _fail(kind, f"{side}={value:.6f}>{hard:.6f}")
            if value > preferred:
                soft.append(side)
        result = _pass(kind)
        if soft:
            result["soft_limit"] = soft
        return result

    if kind == "scalar_range":
        scalars = state.get("scalars", {})
        name = check["name"]
        if name not in scalars:
            return _fail(kind, f"missing:{name}")
        value = float(scalars[name])
        minimum = float(check["min"])
        maximum = float(check["max"])
        if value < minimum or value > maximum:
            return _fail(kind, f"{name}={value:.6f}")
        return _pass(kind)

    if kind == "support_polygon_com":
        com = state.get("com")
        polygon = state.get("support_polygon")
        if com is None or polygon is None:
            return _fail(kind, "missing COM/support_polygon")
        if not _inside_convex_polygon(com, polygon):
            return _fail(kind, f"com={com}")
        return _pass(kind)

    if kind == "joint_limits":
        bone_constraints = constraint_profile["bone_constraints"]
        for bone_name, dofs in state.get("joint_dofs", {}).items():
            if bone_name not in bone_constraints:
                return _fail(kind, f"unknown bone:{bone_name}")
            joint_class = bone_constraints[bone_name]["joint_class"]
            for dof_name, value in dofs.items():
                result = evaluate_dof(constraint_profile, joint_class, dof_name, value)
                if result.status == "HARD_LIMIT":
                    return _fail(kind, f"{bone_name}.{dof_name}={value}")
        return _pass(kind)

    raise ValueError(f"Unknown pose validator: {kind}")


def validate_pose(
    state: dict,
    pose_contract: dict,
    constraint_profile: dict,
    canonical_profile: dict,
) -> dict:
    results = [
        validate_check(state, check, constraint_profile, canonical_profile)
        for check in pose_contract["checks"]
    ]
    failures = [item for item in results if not item["passed"]]
    return {
        "status": "FAIL" if failures else "PASS",
        "results": results,
        "failed_validators": [item["validator"] for item in failures],
    }
