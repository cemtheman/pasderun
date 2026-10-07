"""Declared quasistatic weight-transfer intent; contact is separate from load."""
import math
from lower_body_foundation_motion import minimum_jerk

def transfer_intent(t):
    if not math.isfinite(t) or not 0<=t<=1:raise ValueError('Invalid transfer time')
    p=minimum_jerk(t)
    return {'progress':p,'pelvis_left_displacement':.08*p,
            'left_knee_flexion_deg':16+4*p,
            'contact_roles':{'left':'SUPPORT','right':'TOUCH' if t==1 else 'SUPPORT'},
            'contacts':{'left':'FULL_FOOT','right':'FULL_FOOT'},
            'scope':'quasistatic support eligibility, not measured ground-reaction forces'}

def weightbearing_roles(contact_roles):
    if set(contact_roles)!={'left','right'} or any(r not in ('SUPPORT','TOUCH') for r in contact_roles.values()):raise ValueError('Invalid contact/load roles')
    if 'SUPPORT' not in contact_roles.values():raise ValueError('Weightbearing support required')
    return {s:'SUPPORT' if r=='SUPPORT' else 'SWING' for s,r in contact_roles.items()}
