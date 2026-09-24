"""Measured-sole, length-preserving candidate targets for the guide's feet."""

from __future__ import annotations

import math

from schema_validation import require
from static_pose import add, dot, length, mul, solve_two_link, sub


FOOT_POSITIONS = ("first", "second", "third_left_front", "third_right_front",
                  "fourth_left_front", "fourth_right_front", "fifth_left_front", "fifth_right_front")


def _rotate_up(vector, frame, angle):
    """Rotate left/front components while retaining measured sole height."""
    lateral, anterior = dot(vector, frame["left"]), dot(vector, frame["front"])
    c, s = math.cos(angle), math.sin(angle)
    return add(add(mul(frame["left"], lateral * c + anterior * s),
                   mul(frame["front"], anterior * c - lateral * s)),
               mul(frame["up"], dot(vector, frame["up"])))


def _sole_measurements(sole, frame):
    points = [point["position_armature_local"] for point in sole["points"]]
    require(len(points) >= 3, "sole", "insufficient measured sole vertices")
    front = [dot(p, frame["front"]) for p in points]
    left = [dot(p, frame["left"]) for p in points]
    foot_length, width = max(front) - min(front), max(left) - min(left)
    require(foot_length > .01 and width > .005, "sole", "degenerate rest footprint")
    rear = [p for p in points if dot(p, frame["front"]) <= min(front) + .15 * foot_length]
    heel = mul([sum(p[i] for p in rear) for i in range(3)], 1 / len(rear))
    return {"heel": heel, "length": foot_length, "width": width}


def guide_foot_position(calibration: dict, soles: dict, name: str) -> dict:
    """Propose grounded heels with hip-to-ankle segment lengths intact.

    Fixed pelvis and small turnout are explicitly provisional. A crossed
    target that cannot be reached is rejected instead of twisting a knee.
    """
    require(name in FOOT_POSITIONS, "feet", "unknown guide position")
    frame = calibration["anatomical_frame"]
    bones = calibration["canonical_bones"]
    measured = {side: _sole_measurements(soles[side], frame) for side in ("left", "right")}
    width = max(item["width"] for item in measured.values())
    foot_length = sum(item["length"] for item in measured.values()) / 2
    hips = {side: bones[f"{side}_upper_leg"]["head_local"] for side in ("left", "right")}
    hip_span = abs(dot(sub(hips["left"], hips["right"]), frame["left"]))
    require(hip_span > width, "feet", "hip span narrower than measured sole width")
    rest_heel_front = sum(dot(measured[side]["heel"], frame["front"])
                          for side in ("left", "right")) / 2
    first_half = max(width * .57, hip_span * .16)
    second_half = max(hip_span * .5, width * 1.15)
    heel_goals = {"left": [first_half, rest_heel_front],
                  "right": [-first_half, rest_heel_front]}
    if name == "second":
        heel_goals = {"left": [second_half, rest_heel_front],
                      "right": [-second_half, rest_heel_front]}
    elif name.startswith(("third_", "fourth_", "fifth_")):
        lead = "left" if "left_front" in name else "right"
        back = "right" if lead == "left" else "left"
        if name.startswith("third_"):
            heel_goals[lead] = [heel_goals[back][0] + (width * .32 if lead == "left" else -width * .32),
                                rest_heel_front + foot_length * .43]
        elif name.startswith("fourth_"):
            heel_goals[lead][1] += foot_length * .8
        else:
            heel_goals[lead] = [heel_goals[back][0] + (width * .3 if lead == "left" else -width * .3),
                                rest_heel_front + foot_length * .9]
    targets = {}
    for side in ("left", "right"):
        hip, knee, ankle, ball = (bones[f"{side}_{key}"]["head_local"]
                                 for key in ("upper_leg", "lower_leg", "foot", "toes"))
        rest_heel = measured[side]["heel"]
        toe_vector = sub(ball, ankle)
        rest_angle = math.atan2(dot(toe_vector, frame["left"]),
                                dot(toe_vector, frame["front"]))
        outward_sign = 1 if side == "left" else -1
        # Modest hip-driven turnout *candidate*. No physiological range is inferred.
        angle = math.radians(outward_sign * 24) - rest_angle
        rotated_heel_offset = _rotate_up(sub(rest_heel, ankle), frame, angle)
        x, z = heel_goals[side]
        target_heel = add(add(mul(frame["left"], x), mul(frame["front"], z)),
                          mul(frame["up"], dot(rest_heel, frame["up"])))
        target_ankle = sub(target_heel, rotated_heel_offset)
        outward = frame["left"] if side == "left" else mul(frame["left"], -1)
        pole = add(frame["front"], mul(outward, .35))
        target_ball = add(target_ankle, _rotate_up(toe_vector, frame, angle))
        targets[side] = {"hip_rest": hip, "knee_rest": knee, "ankle_rest": ankle,
                         "ankle": target_ankle, "ball": target_ball,
                         "heel": target_heel, "pole": pole,
                         "turnout_deg": outward_sign * 24,
                         "reach": length(sub(knee, hip)) + length(sub(ankle, knee)),
                         "bone_names": [bones[f"{side}_{part}"]["rig_bone"]
                                        for part in ("upper_leg", "lower_leg", "foot", "toes")]}
    # Crossed foot targets may need a small common plié. Search only a bounded
    # downward translation of the whole pelvis, leaving both heels planted.
    common_reach = min(target["reach"] for target in targets.values())
    legs = None
    pelvis_drop = None
    for step in range(16):
        drop = step * common_reach * .01
        candidate = {}
        try:
            for side, target in targets.items():
                hip = sub(target["hip_rest"], mul(frame["up"], drop))
                knee_rest = sub(target["knee_rest"], mul(frame["up"], drop))
                ankle_rest = sub(target["ankle_rest"], mul(frame["up"], drop))
                solved = solve_two_link(hip, knee_rest, ankle_rest, target["ankle"],
                                        target["pole"], f"{name} {side} leg")
                require(dot(sub(solved["elbow"], hip), frame["front"]) >
                        min(0, dot(sub(target["ankle"], hip), frame["front"])),
                        side, "knee bends behind the intended leg line")
                candidate[side] = {"hip": hip, "knee": solved["elbow"],
                                   "ankle": target["ankle"], "ball": target["ball"],
                                   "heel": target["heel"], "turnout_deg": target["turnout_deg"],
                                   "reach": target["reach"], "bone_names": target["bone_names"]}
        except ValueError:
            continue
        legs, pelvis_drop = candidate, drop
        break
    require(legs is not None, name, "both feet cannot be planted within bounded pelvis drop")
    return {"pose_id": name, "legs": legs,
            "pelvis_drop": pelvis_drop,
            "method": "Measured rest heel, modest hip-origin turnout and length-preserving knee solve; contact needs mesh QA"}


def sample_foot_transition(start: dict, end: dict, frame: dict,
                           count: int = 25) -> list[dict]:
    """Lower into a bounded plié before moving heels; re-solve planted legs."""
    require(isinstance(count, int) and count >= 3, "feet", "invalid transition grid")
    reach = min(start["legs"][side]["reach"] for side in ("left", "right"))
    travel_drop = None
    for step in range(16):
        candidate = max(start["pelvis_drop"], end["pelvis_drop"], step * reach * .01)
        feasible = True
        for index in range(1, count - 1):
            fraction = min(1, max(0, (index / (count - 1) - .2) / .6))
            eased = fraction * fraction * (3 - 2 * fraction)
            for side in ("left", "right"):
                a, b = start["legs"][side], end["legs"][side]
                hip = add(a["hip"], mul(frame["up"], start["pelvis_drop"] - candidate))
                ankle = add(mul(a["ankle"], 1 - eased), mul(b["ankle"], eased))
                distance = math.dist(hip, ankle)
                upper, lower = math.dist(a["hip"], a["knee"]), math.dist(a["knee"], a["ankle"])
                if not abs(upper - lower) + 1e-5 < distance < upper + lower - 1e-5:
                    feasible = False
                    break
            if not feasible:
                break
        if feasible:
            travel_drop = candidate
            break
    require(travel_drop is not None, "feet", "crossing path exceeds bounded common plié")
    result = []
    for index in range(count):
        t = index / (count - 1)
        moving_t = min(1, max(0, (t - .2) / .6))
        eased = moving_t * moving_t * (3 - 2 * moving_t)
        if t < .2:
            lead = (t / .2) ** 2 * (3 - 2 * t / .2)
            drop = start["pelvis_drop"] * (1 - lead) + travel_drop * lead
        elif t <= .8:
            drop = travel_drop
        else:
            tail = ((t - .8) / .2) ** 2 * (3 - 2 * (t - .8) / .2)
            drop = travel_drop * (1 - tail) + end["pelvis_drop"] * tail
        legs = {}
        for side in ("left", "right"):
            a, b = start["legs"][side], end["legs"][side]
            require(abs(a["reach"] - b["reach"]) < 1e-6, side, "leg reach changed")
            if index == 0:
                leg = a.copy()
            elif index == count - 1:
                leg = b.copy()
            else:
                hip = add(a["hip"], mul(frame["up"], start["pelvis_drop"] - drop))
                ankle = add(mul(a["ankle"], 1 - eased), mul(b["ankle"], eased))
                pole = add(mul(sub(a["knee"], a["hip"]), 1 - eased),
                           mul(sub(b["knee"], b["hip"]), eased))
                drop_shift = mul(frame["up"], start["pelvis_drop"] - drop)
                knee_rest = add(a["knee"], drop_shift)
                ankle_rest = add(a["ankle"], drop_shift)
                knee = solve_two_link(hip, knee_rest, ankle_rest, ankle, pole,
                                      f"{start['pose_id']}→{end['pose_id']} {index} {side}")["elbow"]
                toe = add(mul(sub(a["ball"], a["ankle"]), 1 - eased),
                          mul(sub(b["ball"], b["ankle"]), eased))
                require(length(toe) > 1e-8, side, "foot facing vanished")
                ball = add(ankle, mul(toe, math.dist(a["ankle"], a["ball"]) / length(toe)))
                heel = add(mul(a["heel"], 1 - eased), mul(b["heel"], eased))
                leg = {**a, "hip": hip, "knee": knee, "ankle": ankle,
                       "ball": ball, "heel": heel}
            legs[side] = leg
        result.append({"pose_id": f"{start['pose_id']}_to_{end['pose_id']}",
                       "pelvis_drop": drop, "legs": legs})
    return result
