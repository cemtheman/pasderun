"""Phase 10.6.3 anatomical constraint evaluator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConstraintResult:
    status: str
    joint_class: str
    dof: str
    value_deg: float
    preferred_min: float | None
    preferred_max: float | None
    hard_min: float | None
    hard_max: float | None


def evaluate_dof(
    constraint_spec: dict,
    joint_class: str,
    dof: str,
    value_deg: float,
) -> ConstraintResult:
    joint = constraint_spec["joint_limits"][joint_class]
    if joint.get("unbounded"):
        allowed = set(joint.get("unbounded_dofs", []))
        if dof not in allowed:
            raise ValueError(
                f"Undeclared DOF {joint_class}.{dof}; motion authority denied."
            )
        return ConstraintResult(
            "PASS",
            joint_class,
            dof,
            float(value_deg),
            None,
            None,
            None,
            None,
        )

    dofs = joint.get("dofs", {})
    if dof not in dofs:
        raise ValueError(
            f"Undeclared DOF {joint_class}.{dof}; motion authority denied."
        )

    limits = dofs[dof]
    hard_min = float(limits["hard"]["min"])
    hard_max = float(limits["hard"]["max"])
    preferred_min = float(limits["preferred"]["min"])
    preferred_max = float(limits["preferred"]["max"])
    value = float(value_deg)

    if value < hard_min or value > hard_max:
        status = "HARD_LIMIT"
    elif value < preferred_min or value > preferred_max:
        status = "SOFT_LIMIT"
    else:
        status = "PASS"

    return ConstraintResult(
        status,
        joint_class,
        dof,
        value,
        preferred_min,
        preferred_max,
        hard_min,
        hard_max,
    )


def knee_external_rotation_cap_deg(
    constraint_spec: dict,
    knee_flexion_deg: float,
) -> float:
    policy = constraint_spec["turnout_model"]["knee_axial_coupling"]
    start = float(policy["max_external_rotation_at_extension_deg"])
    end = float(policy["max_external_rotation_at_90_flexion_deg"])
    flexion = min(max(float(knee_flexion_deg), 0.0), 90.0)
    return start + (end - start) * (flexion / 90.0)


def validate_turnout_request(
    constraint_spec: dict,
    hip_external_rotation_deg: float,
    knee_external_rotation_deg: float,
    knee_flexion_deg: float,
    independent_foot_yaw_deg: float,
) -> dict:
    hip_policy = constraint_spec["turnout_model"]["hip_external_rotation"]
    hip = float(hip_external_rotation_deg)
    knee = float(knee_external_rotation_deg)
    foot_yaw = float(independent_foot_yaw_deg)

    violations: list[str] = []
    warnings: list[str] = []

    if hip < 0.0:
        violations.append("hip_external_rotation_must_be_nonnegative")
    if hip > float(hip_policy["hard_max_per_leg_deg"]):
        violations.append("hip_external_rotation_hard_limit")
    elif hip > float(hip_policy["preferred_max_per_leg_deg"]):
        warnings.append("hip_external_rotation_soft_limit")

    knee_cap = knee_external_rotation_cap_deg(
        constraint_spec,
        knee_flexion_deg,
    )
    if knee < 0.0:
        violations.append("knee_external_rotation_must_be_nonnegative")
    if knee > knee_cap + 1e-9:
        violations.append("knee_axial_coupling_exceeded")

    if abs(foot_yaw) > 1e-9:
        violations.append("independent_foot_yaw_forbidden")

    status = "HARD_LIMIT" if violations else (
        "SOFT_LIMIT" if warnings else "PASS"
    )
    return {
        "status": status,
        "hip_external_rotation_deg": hip,
        "knee_external_rotation_deg": knee,
        "knee_external_rotation_cap_deg": round(knee_cap, 8),
        "knee_flexion_deg": float(knee_flexion_deg),
        "independent_foot_yaw_deg": foot_yaw,
        "warnings": warnings,
        "violations": violations,
    }


def validate_limit_table(
    canonical_spec: dict,
    constraint_spec: dict,
) -> list[str]:
    errors: list[str] = []
    classes = canonical_spec["joint_classes"]
    limits = constraint_spec["joint_limits"]

    for class_name, class_spec in classes.items():
        if class_name not in limits:
            errors.append(f"missing_joint_class:{class_name}")
            continue

        declared = set(class_spec["rotational_dofs"])
        joint_limits = limits[class_name]
        if joint_limits.get("unbounded"):
            configured = set(joint_limits.get("unbounded_dofs", []))
        else:
            configured = set(joint_limits.get("dofs", {}))
        if declared != configured:
            errors.append(
                f"dof_mismatch:{class_name}:"
                f"declared={sorted(declared)}:"
                f"configured={sorted(configured)}"
            )

        for dof_name, dof_limits in joint_limits.get("dofs", {}).items():
            hard = dof_limits["hard"]
            preferred = dof_limits["preferred"]
            if float(hard["min"]) > float(preferred["min"]):
                errors.append(
                    f"preferred_below_hard_min:{class_name}.{dof_name}"
                )
            if float(preferred["max"]) > float(hard["max"]):
                errors.append(
                    f"preferred_above_hard_max:{class_name}.{dof_name}"
                )
            if float(preferred["min"]) > float(preferred["max"]):
                errors.append(
                    f"preferred_inverted:{class_name}.{dof_name}"
                )
            if float(hard["min"]) > float(hard["max"]):
                errors.append(
                    f"hard_inverted:{class_name}.{dof_name}"
                )

    extra = set(limits) - set(classes)
    for class_name in sorted(extra):
        errors.append(f"extra_joint_class:{class_name}")

    return errors
