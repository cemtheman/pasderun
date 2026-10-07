"""Observed planar support geometry; no authored balance scalar authority."""
import math


def point2(value):
    if len(value) != 2 or not all(math.isfinite(x) for x in value):
        raise ValueError('Expected finite planar point')
    return tuple(value)


def convex_hull(points):
    points = sorted(set(point2(p) for p in points))
    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    halves = []
    for sequence in (points, list(reversed(points))):
        half = []
        for p in sequence:
            while len(half) >= 2 and cross(half[-2], half[-1], p) <= 0:
                half.pop()
            half.append(p)
        halves.append(half)
    hull = halves[0][:-1]+halves[1][:-1]
    if len(hull) < 3:
        raise ValueError('Degenerate support area')
    return hull


def balance_diagnostics(support_points, projected_com, support_roles):
    if set(support_roles) != {'left', 'right'} or any(r not in ('SUPPORT', 'SWING') for r in support_roles.values()):
        raise ValueError('Explicit bilateral support roles required')
    active = [s for s, r in support_roles.items() if r == 'SUPPORT']
    if not active:
        raise ValueError('Static balance requires support')
    hull = convex_hull([p for s in active for p in support_points[s]])
    c = point2(projected_com)
    margins = []
    for a, b in zip(hull, hull[1:]+hull[:1]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        margins.append((dx*(c[1]-a[1])-dy*(c[0]-a[0]))/math.hypot(dx, dy))
    margin = min(margins)
    return {'status': 'PASS' if margin >= 0 else 'OUTSIDE_SUPPORT',
            'support_polygon': hull, 'projected_com_proxy': c,
            'signed_balance_margin': margin, 'support_roles': dict(support_roles),
            'scope': 'surface-density geometry proxy; not tissue-mass COM or dynamic stability'}
