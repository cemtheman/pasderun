"""Nonpromotable sole/contact parameter diagnostic; no threshold changes."""
import sys,json,copy,math,statistics
from pathlib import Path
repo=Path(__file__).resolve().parents[2];sys.path[:0]=[str(repo/'tools/blender'),str(repo/'tools/ballet_motion')]
from bbm_body_runtime_v1 import BodyRuntime,gate
from render_bbm3_foot_v1 import apply_calibrated_basis
from distributed_turnout_v1 import derive_turnout
from mathutils import Matrix,Vector
body=BodyRuntime();approved=[json.loads((repo/'build/visual_validation/BBM-5/report.json').read_text())['samples'][f'candidate/{i:02d}']['canonical_state'] for i in range(25)]
initial=body.realize(approved[0],{'left':'SUPPORT','right':'SUPPORT'})
points=[p for s in ('left','right') for r in ('fore','rear') for p in gate.static_core.evaluated_sample_points(body.rig,body.runtime['anchors'][s][r])];floor=min(p.dot(body.up) for p in points)
records=[]
for knee in (0,8):
 for angle,toe in [(a,t) for a in (25,30,35,40,45,50) for t in (0,15,25,35)]:
  state=copy.deepcopy(approved[0]);a,b=next((a,b) for a,b in zip(approved,approved[1:]) if a['joint_dofs']['left_shin']['flexion_extension']<=knee<=b['joint_dofs']['left_shin']['flexion_extension']);lo=a['joint_dofs']['left_shin']['flexion_extension'];hi=b['joint_dofs']['left_shin']['flexion_extension'];p=(knee-lo)/(hi-lo)
  for side in ('left','right'):
   for dof in ('flexion_extension','abduction_adduction'):state['joint_dofs'][f'{side}_thigh'][dof]=a['joint_dofs'][f'{side}_thigh'][dof]+p*(b['joint_dofs'][f'{side}_thigh'][dof]-a['joint_dofs'][f'{side}_thigh'][dof])
   state['joint_dofs'][f'{side}_shin']['flexion_extension']=knee;state['turnout'][side].update({'knee_flexion_deg':knee,'knee_external_rotation_deg':derive_turnout(body.constraints,45,knee)['knee_external_rotation_deg']})
  seed=body.realize(state,{'left':'SUPPORT','right':'SUPPORT'})
  for side in ('left','right'):
   for key,rot in ((f'{side}_foot',-(body.neutral[side]+angle)),(f'{side}_toes',toe)):
    bone=body.canonical['canonical_bones'][key];parent,rest=gate.static_core.canonical_parent_and_rest_local(body.rig,body.canonical,key);desired=(parent@rest@Matrix.Rotation(math.radians(rot),3,'X')).to_quaternion().normalized().to_matrix();apply_calibrated_basis(body.rig,bone['rig_bone'],gate.static_core.rig_basis_from_canonical_pose(bone,desired))
  heights=gate.static_core.contact_heights(body.rig,body.runtime['anchors'],body.up,body.q);shift=statistics.median(body.runtime['rest_heights'][s]['fore']-heights[s]['fore'] for s in ('left','right'));translation=Vector(seed['root_translation'])+body.up*shift;gate.static_core.set_root_translation_armature_space(body.rig,body.canonical['canonical_bones']['pelvis']['rig_bone'],translation)
  mins={s:{r:min(p.dot(body.up)-floor for p in gate.static_core.evaluated_sample_points(body.rig,body.runtime['anchors'][s][r])) for r in ('rear','fore')} for s in ('left','right')}
  records.append({'knee':knee,'angle':angle,'toe':toe,'minima':mins,'min':min(v for rs in mins.values() for v in rs.values())})
print(json.dumps(records,indent=2));(repo/'build/visual_validation/BBM-6/release-contact-probe.json').write_text(json.dumps(records,indent=2))
