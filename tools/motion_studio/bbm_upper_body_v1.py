"""Bounded phrase coordination over the accepted arm solver.

Offsets change bend-pole and hand intent timing, never bone lengths. Scapular
participation is semantic on this rig; measured Clavicle bones realize carriage.
"""
import copy
import math
from static_pose import add, sub, mul, length, solve_two_link
from elbow_flexion import inward_flexion


def lagged_phase(t, lag):
    if not math.isfinite(t) or not math.isfinite(lag) or not 0 <= t <= 1 or not 0 <= lag <= .15:
        raise ValueError('Phase or lag outside BBM working envelope')
    # Both landmarks remain exact; the lag disappears smoothly at endpoints.
    return t - lag * math.sin(math.pi * t)**2


def coordinate_samples(samples, frame, elbow_lag=.035, hand_lag=.06, preserve_elbow_path=False):
    if len(samples)!=49:raise ValueError('BBM v1 requires the locked 49-sample review grid')
    result=copy.deepcopy(samples)
    for i,sample in enumerate(result):
        leg=0 if i<=24 else 1
        t=(i if leg==0 else i-24)/24
        sample['coordination']={'elbow_phase':lagged_phase(t,elbow_lag),
                                'hand_phase':lagged_phase(t,hand_lag),
                                'head_phase':lagged_phase(t,.1),
                                'clavicle_carriage_deg':.35*math.sin(math.pi*t)**2,
                                'scapula_semantics':'carriage coupling; no separate scapula bone'}
        if t in (0,1):continue
        start=samples[0 if leg==0 else 24];end=samples[24 if leg==0 else 48]
        for side,arm in sample['arms'].items():
            a,b=start['arms'][side],end['arms'][side]
            p=sample['coordination']['elbow_phase'];p=p*p*(3-2*p)
            pole=add(mul(sub(a['elbow'],a['shoulder']),1-p),mul(sub(b['elbow'],b['shoulder']),p))
            if preserve_elbow_path:
                pos=24*sample['coordination']['elbow_phase'];lo=int(pos);hi=min(24,lo+1);weight=pos-lo
                pa=samples[leg*24+lo]['arms'][side];pb=samples[leg*24+hi]['arms'][side]
                pole=add(mul(sub(pa['elbow'],pa['shoulder']),1-weight),mul(sub(pb['elbow'],pb['shoulder']),weight))
            solved=solve_two_link(arm['shoulder'],a['elbow'],a['wrist'],arm['wrist'],pole,side)
            arm['elbow']=solved['elbow']
            p=sample['coordination']['hand_phase'];p=p*p*(3-2*p)
            direction=add(mul(sub(a['hand'],a['wrist']),1-p),mul(sub(b['hand'],b['wrist']),p))
            arm['hand']=add(arm['wrist'],mul(direction,length(sub(a['hand'],a['wrist']))/length(direction)))
            inward=mul(frame['left'],-1 if side=='left' else 1)
            inward_flexion(arm,inward,side)
    return result
