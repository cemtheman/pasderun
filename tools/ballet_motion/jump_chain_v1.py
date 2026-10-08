"""Bounded four-state vertical jump intent on the existing minimum-jerk law."""
import math
from lower_body_foundation_motion import minimum_jerk

def jump_intent(t,coordinated=True):
    if not math.isfinite(t) or not 0<=t<=1:raise ValueError('Invalid jump time')
    if t<.2:
        phase='PREPARATION';knee=32*minimum_jerk(t/.2);rise=0.;lift=0.;toe=None
    elif t<=.35:
        phase='TAKEOFF';p=(t-.2)/.15
        knee=32*(1-minimum_jerk((t-.2)/.12 if coordinated else p));rise=minimum_jerk((t-.25)/.10 if coordinated else p);lift=0.;toe=None
    elif t<.55:
        phase='FLIGHT';u=(t-.35)/.2;knee=8*minimum_jerk((u-.7)/.3) if coordinated else 0.;rise=1.;lift=4*.18*u*(1-u);toe=35*(1-math.sin(math.pi*u))
    else:
        phase='LANDING';p=1. if t==1 else (t-.55)/.45;impact=8 if coordinated else 0
        knee=impact+(32-impact)*minimum_jerk(p/.4) if p<.4 else 32*(1-minimum_jerk((p-.4)/.6));rise=1-minimum_jerk((t-.55)/.08);lift=0.;toe=None
    flight_ankle=None
    if phase=='FLIGHT':
        u=(t-.35)/.2
        flight_ankle=30+10*minimum_jerk(u/.5) if u<=.5 else 40-15*minimum_jerk((u-.5)/.5)
    ground_ankle=30 if phase=='TAKEOFF' else 25 if phase=='LANDING' else 35
    if not coordinated:
        ground_ankle=35
        if phase=='FLIGHT':flight_ankle=35+5*math.sin(math.pi*(t-.35)/.2)
    return {'state':phase,'knee_flexion_deg':knee,'foot_rise_progress':rise,'flight_clearance':lift,'toe_flexion_deg':35*rise if toe is None else toe,'flight_ankle_plantar_deg':flight_ankle,'ground_push_plantar_deg':ground_ankle,'duration_seconds':2.,'flight_duration_seconds':.4,'effective_clearance_gravity':9.,'scope':'kinematic clearance parabola; no force simulation'}

def jump_review_times(dense=False):
    """Include exact release/contact and their immediate neighbours."""
    if not dense:return [i/48 for i in range(49)]
    return sorted(set([i/96 for i in range(97)]+[.1,.2,.25,.32,.35,.45,.49,.55,.63,.73]+[t+offset for t in (.2,.32,.35,.55,.63,.73) for offset in (-.000001,.000001)]))
