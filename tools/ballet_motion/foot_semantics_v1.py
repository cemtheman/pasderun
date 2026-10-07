"""BBM-3 semantic foot states inside the existing joint envelopes.

Arch/hindfoot fields are intent where the source rig lacks separate bones.
Pointe-ready is a preparation state, never a claim of full en-pointe support.
"""
import math
from anatomical_constraints import evaluate_dof

STATES={'FLAT':('FULL_FOOT','NEUTRAL'), 'DEMI_POINTE':('FOREFOOT','ELONGATED'), 'POINTE_READY':('TOE_REGION_PROXY','ELONGATED')}


def foot_state(constraints,state,plantar_deg,toe_deg,inversion_deg=0):
    if state not in STATES:raise ValueError('Unknown foot semantic state')
    if any(not math.isfinite(v) for v in (plantar_deg,toe_deg,inversion_deg)):raise ValueError('Nonfinite foot intent')
    gates=[evaluate_dof(constraints,'ankle_2dof','plantar_dorsiflexion',plantar_deg),evaluate_dof(constraints,'ankle_2dof','inversion_eversion',inversion_deg),evaluate_dof(constraints,'mtp_hinge','toe_flexion_extension',toe_deg)]
    if any(g.status!='PASS' for g in gates):raise ValueError('Foot intent leaves existing preferred envelope')
    support,arch=STATES[state]
    return {'state':state,'ankle_plantar_dorsiflexion_deg':plantar_deg,'mtp_toe_flexion_extension_deg':toe_deg,
            'hindfoot_inversion_eversion_intent_deg':inversion_deg,'midfoot_arch_intent':arch,'independent_arch_bone':False,
            'support_region':support,'independent_foot_yaw_deg':0,'full_en_pointe_claim':False,
            'retarget_policy':'existing ankle/toe bones only; semantic arch/hindfoot fields never invent bone motion'}


def anatomical_plantar_from_canonical(constraints,canonical_angle_deg,neutral_offset_deg):
    """Decode relative to source-bound flat-contact neutral, without widening ROM."""
    if not all(math.isfinite(v) for v in (canonical_angle_deg,neutral_offset_deg)):
        raise ValueError('Invalid calibrated ankle angle')
    relative=canonical_angle_deg-neutral_offset_deg
    result=evaluate_dof(constraints,'ankle_2dof','plantar_dorsiflexion',relative)
    return {'anatomical_plantar_deg':relative,'canonical_angle_deg':canonical_angle_deg,'neutral_offset_deg':neutral_offset_deg,'status':result.status}
