"""Phase 10.6.6 retarget math helpers."""

from __future__ import annotations

import math

from canonical_math import (
    cross,
    determinant,
    mat_mul,
    normalize,
    orthogonality_error,
    project_orthogonal,
    transpose,
)


def identity3() -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]


def matrix_max_error(a: list[list[float]], b: list[list[float]]) -> float:
    return max(
        abs(float(a[row][col]) - float(b[row][col]))
        for row in range(3)
        for col in range(3)
    )


def axis_rotation(axis: str, angle_deg: float) -> list[list[float]]:
    angle = math.radians(float(angle_deg))
    c = math.cos(angle)
    s = math.sin(angle)

    if axis == "X":
        return [
            [1.0, 0.0, 0.0],
            [0.0, c, -s],
            [0.0, s, c],
        ]
    if axis == "Y":
        return [
            [c, 0.0, s],
            [0.0, 1.0, 0.0],
            [-s, 0.0, c],
        ]
    if axis == "Z":
        return [
            [c, -s, 0.0],
            [s, c, 0.0],
            [0.0, 0.0, 1.0],
        ]
    raise ValueError(f"Unknown local rotation axis: {axis}")


def local_twist_y(
    basis: list[list[float]],
    angle_deg: float,
) -> list[list[float]]:
    return mat_mul(basis, axis_rotation("Y", angle_deg))


def basis_from_length_and_front(
    length_axis: list[float],
    front_seed: list[float],
    up_seed: list[float],
    left_seed: list[float],
) -> list[list[float]]:
    y_axis = normalize(length_axis)

    candidates = (front_seed, up_seed, left_seed)
    best = None
    best_size = -1.0
    for seed in candidates:
        projected = project_orthogonal(seed, y_axis)
        size = sum(value * value for value in projected)
        if size > best_size:
            best = projected
            best_size = size

    if best is None or best_size <= 1e-12:
        raise ValueError("Cannot construct roll-stable basis from segment.")

    z_axis = normalize(best)
    x_axis = normalize(cross(y_axis, z_axis))
    z_axis = normalize(cross(x_axis, y_axis))
    basis = [
        [x_axis[0], y_axis[0], z_axis[0]],
        [x_axis[1], y_axis[1], z_axis[1]],
        [x_axis[2], y_axis[2], z_axis[2]],
    ]
    if determinant(basis) <= 0.0:
        raise ValueError("Constructed basis is not right-handed.")
    return basis


def validate_rotation_matrix(
    matrix: list[list[float]],
    orthogonality_max_error: float,
    determinant_min: float,
    determinant_max: float,
) -> None:
    error = orthogonality_error(matrix)
    det = determinant(matrix)
    if error > float(orthogonality_max_error):
        raise ValueError(f"Rotation orthogonality error {error}.")
    if not float(determinant_min) <= det <= float(determinant_max):
        raise ValueError(f"Rotation determinant {det}.")
