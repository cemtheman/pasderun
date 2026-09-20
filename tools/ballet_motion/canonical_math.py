"""Small dependency-free math kernel for Pas de Run Ballet Motion Engine."""

from __future__ import annotations

import math
from typing import Iterable


Vector3 = list[float]
Matrix3 = list[list[float]]


def vec(values: Iterable[float]) -> Vector3:
    result = [float(value) for value in values]
    if len(result) != 3:
        raise ValueError(f"Expected vec3, got {result}")
    return result


def add(a: Vector3, b: Vector3) -> Vector3:
    return [a[i] + b[i] for i in range(3)]


def sub(a: Vector3, b: Vector3) -> Vector3:
    return [a[i] - b[i] for i in range(3)]


def scale(a: Vector3, amount: float) -> Vector3:
    return [value * float(amount) for value in a]


def dot(a: Vector3, b: Vector3) -> float:
    return sum(a[i] * b[i] for i in range(3))


def cross(a: Vector3, b: Vector3) -> Vector3:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def length(a: Vector3) -> float:
    return math.sqrt(dot(a, a))


def normalize(a: Vector3) -> Vector3:
    size = length(a)
    if size <= 1e-12:
        raise ValueError("Cannot normalize zero vector.")
    return scale(a, 1.0 / size)


def project_orthogonal(value: Vector3, normal: Vector3) -> Vector3:
    n = normalize(normal)
    return sub(value, scale(n, dot(value, n)))


def transpose(matrix: Matrix3) -> Matrix3:
    return [[matrix[row][col] for row in range(3)] for col in range(3)]


def mat_mul(a: Matrix3, b: Matrix3) -> Matrix3:
    return [
        [
            sum(a[row][k] * b[k][col] for k in range(3))
            for col in range(3)
        ]
        for row in range(3)
    ]


def mat_vec(matrix: Matrix3, value: Vector3) -> Vector3:
    return [
        sum(matrix[row][col] * value[col] for col in range(3))
        for row in range(3)
    ]


def matrix_from_columns(x: Vector3, y: Vector3, z: Vector3) -> Matrix3:
    return [
        [x[0], y[0], z[0]],
        [x[1], y[1], z[1]],
        [x[2], y[2], z[2]],
    ]


def determinant(matrix: Matrix3) -> float:
    a, b, c = matrix[0]
    d, e, f = matrix[1]
    g, h, i = matrix[2]
    return (
        a * (e * i - f * h)
        - b * (d * i - f * g)
        + c * (d * h - e * g)
    )


def orthogonality_error(matrix: Matrix3) -> float:
    gram = mat_mul(transpose(matrix), matrix)
    target = [[1.0 if row == col else 0.0 for col in range(3)] for row in range(3)]
    return max(
        abs(gram[row][col] - target[row][col])
        for row in range(3)
        for col in range(3)
    )


def rotation_matrix_to_quaternion_wxyz(matrix: Matrix3) -> list[float]:
    m00, m01, m02 = matrix[0]
    m10, m11, m12 = matrix[1]
    m20, m21, m22 = matrix[2]
    trace = m00 + m11 + m22

    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        w = 0.25 * s
        x = (m21 - m12) / s
        y = (m02 - m20) / s
        z = (m10 - m01) / s
    elif m00 > m11 and m00 > m22:
        s = math.sqrt(1.0 + m00 - m11 - m22) * 2.0
        w = (m21 - m12) / s
        x = 0.25 * s
        y = (m01 + m10) / s
        z = (m02 + m20) / s
    elif m11 > m22:
        s = math.sqrt(1.0 + m11 - m00 - m22) * 2.0
        w = (m02 - m20) / s
        x = (m01 + m10) / s
        y = 0.25 * s
        z = (m12 + m21) / s
    else:
        s = math.sqrt(1.0 + m22 - m00 - m11) * 2.0
        w = (m10 - m01) / s
        x = (m02 + m20) / s
        y = (m12 + m21) / s
        z = 0.25 * s

    quat = [w, x, y, z]
    size = math.sqrt(sum(value * value for value in quat))
    if size <= 1e-12:
        raise ValueError("Degenerate rotation quaternion.")
    quat = [value / size for value in quat]

    # Canonical hemisphere for deterministic JSON/test output.
    if quat[0] < 0.0:
        quat = [-value for value in quat]
    return quat


def rounded_vector(value: Vector3, digits: int = 8) -> Vector3:
    return [round(float(component), digits) for component in value]


def rounded_matrix(value: Matrix3, digits: int = 8) -> Matrix3:
    return [
        [round(float(component), digits) for component in row]
        for row in value
    ]
