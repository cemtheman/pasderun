"""Reusable temporal composition over BBM plié, planted transfer and arm path.

This module declares intent, never claims physical validity. The Blender
adapter must independently measure contact, balance, anatomy and continuity.
"""
import math
from lower_body_foundation_motion import minimum_jerk

BOUNDARIES=(.2,.28,.46,.48,.56,.6,.8,.82)
STYLES={'clear':{'duration_seconds':6.,'upper_lag':.035,'head_lag':.1},
        'soft':{'duration_seconds':7.2,'upper_lag':.06,'head_lag':.12}}

def phase(t,start,end):
    return max(0.,min(1.,minimum_jerk(max(0.,min(1.,(t-start)/(end-start))))))

def delayed(t,lag):
    return t-lag*math.sin(math.pi*t)**2

def phrase_intent(t,style='clear'):
    if not math.isfinite(t) or not 0<=t<=1 or style not in STYLES:
        raise ValueError('Invalid phrase time/style')
    settings=STYLES[style]
    if t<.2:
        primitive='PLIE';plie=.5*phase(t,0,.2);transfer=0.
    elif t<.48:
        primitive='TRANSFER';transfer=phase(t,.2,.48);plie=.5
    elif t<=.56:
        primitive='SUPPORTED_SETTLE';transfer=1.;plie=.5
    elif t<.8:
        primitive='RETURN';transfer=1-phase(t,.56,.8);plie=.5
    else:
        primitive='CLOSURE';transfer=0.;plie=.5*(1-phase(t,.8,1))
    # First port de bras breath overlaps lower primitives; no clip resets.
    u=delayed(t,settings['upper_lag'])
    if u<.28:arm=phase(u,0,.28)
    elif u<.46:arm=1-phase(u,.28,.46)
    elif u<.6:arm=0.
    elif u<.82:arm=phase(u,.6,.82)
    else:arm=1-phase(u,.82,1)
    h=delayed(t,settings['head_lag'])
    gaze=phase(h,.2,.48)*(1-phase(h,.56,.8))
    return {'primitive':primitive,'plie_coordinate':plie,
            'transfer_coordinate':transfer,'arm_coordinate':arm,
            'head_yaw_deg':4*gaze,'duration_seconds':settings['duration_seconds'],
            'roles':{'left':'SUPPORT','right':'TOUCH' if .48<=t<=.56 else 'SUPPORT'},
            'contact_policy':'FULL_FOOT','style':style,
            'start_state':'closed first / straight knees / bras bas / bilateral support',
            'end_state':'closed first / straight knees / bras bas / bilateral support',
            'scope':'quasistatic planted phrase; no ground reaction force measurement'}

def review_times(dense=True):
    times={i/72 for i in range(73)}|set(BOUNDARIES)
    if dense:times|={t+d for t in BOUNDARIES for d in (-1e-6,1e-6)}
    return sorted(times)
