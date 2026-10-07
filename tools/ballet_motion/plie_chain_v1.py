"""Bounded engine phrasing over the existing minimum-jerk time law."""
import math
from lower_body_foundation_motion import minimum_jerk

def plie_progress(t,lag=0):
    if not math.isfinite(t) or not math.isfinite(lag) or not 0<=t<=1 or not -.1<=lag<=.1:
        raise ValueError('Invalid normalized phrase input')
    leg=2*t if t<=.5 else 2*(1-t)
    shifted=leg-lag*math.sin(math.pi*leg)**2
    return minimum_jerk(shifted)

def chain_intent(t):
    return {'knee_flexion_deg':32*plie_progress(t),
            'hip_reference_flexion_deg':18*plie_progress(t,-.025),
            'closure_progress':plie_progress(t,.015),
            'hip_external_rotation_deg':45,'independent_foot_yaw_deg':0}
