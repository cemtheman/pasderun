"""Isolated BBM-2 chain semantics; foot progression is measured output.

The coupling share is an engine policy inside the existing flexion-dependent
cap, not an empirical estimate of an individual dancer's tibial rotation.
"""
import math
from anatomical_constraints import knee_external_rotation_cap_deg, validate_turnout_request


def derive_turnout(constraints, hip_external_rotation_deg, knee_flexion_deg, coupling_share=.5):
    values=(hip_external_rotation_deg,knee_flexion_deg,coupling_share)
    if any(not math.isfinite(v) for v in values) or knee_flexion_deg<0 or not 0<=coupling_share<=1:
        raise ValueError('Invalid turnout input')
    preferred=constraints['turnout_model']['hip_external_rotation']['preferred_max_per_leg_deg']
    hip=hip_external_rotation_deg
    cap=knee_external_rotation_cap_deg(constraints,knee_flexion_deg)
    knee=cap*min(1,max(0,hip/preferred))*coupling_share
    result=validate_turnout_request(constraints,hip,knee,knee_flexion_deg,0)
    result['authority']='HIP_PRIMARY_KNEE_DERIVED_FOOT_OBSERVED'
    result['coupling_share_engine_policy']=coupling_share
    return result


def planar_angle_deg(a,b,up):
    def projected(v):
        d=sum(x*y for x,y in zip(v,up));p=[x-d*y for x,y in zip(v,up)]
        length=math.sqrt(sum(x*x for x in p))
        if length<1e-8:raise ValueError('Degenerate tracking projection')
        return [x/length for x in p]
    if abs(sum(v*v for v in up)-1)>1e-6:raise ValueError('Up axis must be normalized')
    pa,pb=projected(a),projected(b)
    return math.degrees(math.acos(max(-1,min(1,sum(x*y for x,y in zip(pa,pb))))))


def alignment_diagnostics(constraints,knee_heading,toe_ray,body_front,up,pelvis_yaw_deg=0,trunk_tilt_deg=0,arch_collapse=None):
    error=planar_angle_deg(knee_heading,toe_ray,up)
    policy=constraints['coupling_constraints']['knee_second_toe_tracking']
    status='HARD_LIMIT' if error>policy['hard_angular_error_deg'] else ('SOFT_LIMIT' if error>policy['preferred_angular_error_deg'] else 'PASS')
    return {'status':status,'observed_knee_toe_error_deg':error,'observed_foot_progression_abs_deg':planar_angle_deg(body_front,toe_ray,up),
            'pelvis_yaw_deg':pelvis_yaw_deg,'trunk_tilt_deg':trunk_tilt_deg,'arch_collapse':arch_collapse,
            'arch_observation':'NOT_MEASURABLE_ON_CURRENT_RIG' if arch_collapse is None else 'MEASURED',
            'tracking_reference':'canonical shin anterior axis versus toe-bone longitudinal ray; second-toe proxy, not separate digit measurement'}
