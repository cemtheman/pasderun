"""Bounded four-state vertical jump intent on the existing minimum-jerk law."""
import math
from lower_body_foundation_motion import minimum_jerk

def jump_intent(t,coordinated=True):
    if not math.isfinite(t) or not 0<=t<=1:raise ValueError('Invalid jump time')
    if t<.2:
        phase='PREPARATION';knee=32*minimum_jerk(t/.2);rise=0.;lift=0.;toe=None
    elif t<.35:
        phase='TAKEOFF';p=(t-.2)/.15
        knee=32*(1-minimum_jerk((t-.2)/.12 if coordinated else p));rise=minimum_jerk((t-.25)/.10 if coordinated else p);lift=0.;toe=None
    elif t<.55:
        phase='FLIGHT';u=(t-.35)/.2;knee=8*minimum_jerk((u-.7)/.3) if coordinated else 0.;rise=1.;lift=4*.18*u*(1-u);toe=35*(1-math.sin(math.pi*u))
    else:
        phase='LANDING';p=1. if t==1 else (t-.55)/.45;impact=8 if coordinated else 0
        knee=impact+(32-impact)*minimum_jerk(p/.4) if p<.4 else 32*(1-minimum_jerk((p-.4)/.6));rise=1-minimum_jerk((t-.55)/.08);lift=0.;toe=None
    return {'state':phase,'knee_flexion_deg':knee,'foot_rise_progress':rise,'flight_clearance':lift,'toe_flexion_deg':35*rise if toe is None else toe,'flight_ankle_plantar_deg':35+5*math.sin(math.pi*(t-.35)/.2) if phase=='FLIGHT' else None,'duration_seconds':2.,'flight_duration_seconds':.4,'effective_clearance_gravity':9.,'scope':'kinematic clearance parabola; no force simulation'}
