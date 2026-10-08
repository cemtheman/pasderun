"""Build source-bound runtime payload from immutable accepted BBM-7 samples.
No accepted solver, render, or validation is rerun.
"""
import sys,json,hashlib,math
from pathlib import Path
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/ballet_motion'))
from build_canonical_ballet_profile_v1 import build_bone_entry
load=lambda p:json.loads(p.read_text())
bridge=load(ROOT/'build/visual_validation/BBM-8/environment-probe/bridge_candidate.json')
report=load(ROOT/'build/visual_validation/BBM-7/candidate-01/report.json')
cal=load(ROOT/'build/visual_validation/BBM-1/calibration.json')
spec=load(ROOT/'assets/ballet_motion/canonical_ballet_skeleton_v1.json')
canonical={n:build_bone_entry(n,s,cal['canonical_bones'][n],cal['anatomical_frame'],cal['canonical_bones']['pelvis']['head_local'],spec['validator_foundation']) for n,s in spec['bones'].items()}
C=Matrix(((1,0,0),(0,0,1),(0,-1,0)))
byname={b['blender_name']:i for i,b in enumerate(bridge['bones'])}
def conversion(key):
 b=canonical[key];i=byname[b['rig_bone']];right=Matrix(bridge['bones'][i]['right_bind']).inverted();left=C.inverted()
 if b['joint_class'] in ('BALL_3DOF','HINGE_WITH_TWIST','SPINE_3DOF','NECK_3DOF','CLAVICLE_3DOF'):
  # Use the exact existing authority's joint-class membership below.
  pass
 sys.path.insert(0,str(ROOT/'tools/blender'))
 import apply_static_foundation_poses_v1 as core
 if b['joint_class'] in core.SEMANTIC_LENGTH_AXIS_JOINT_CLASSES:
  right=right@core.rotation_y(-core.semantic_roll_offset_y(b))
 else:left=Matrix(b['retarget_bind']['canonical_to_rig_rotation_matrix']).inverted()@left
 return {'bone':i,'left':[list(r) for r in left],'right':[list(r) for r in right]}
wrists={}
for side in ('left','right'):
 h=canonical[side+'_hand'];p=canonical[h['parent']]
 wrists[side]={'hand':conversion(side+'_hand'),'parent':conversion(h['parent']), 'rest_local':[list(r) for r in Matrix(p['canonical_rest_contract']['basis_armature_local']).transposed()@Matrix(h['canonical_rest_contract']['basis_armature_local'])]}
for i,f in enumerate(bridge['frames']):f['wrist']=report['samples'][f'clear/{i:03d}']['wrist']
bridge['conversions']={k:conversion(k) for k in canonical}
bridge.update(schema=2,status='BBM8_RUNTIME_CANDIDATE_REQUIRES_NEW_GEOMETRY_AND_VISUAL_PROOF',wrists=wrists,canonical=canonical)
for name,path in {'source_glb_sha256':'assets/characters/low_poly_girl/low_poly_girl .glb','accepted_report_sha256':'build/visual_validation/BBM-7/candidate-01/report.json'}.items():
 assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==bridge[name],name
out=ROOT/'assets/bbm8/clear6s_runtime_candidate.json'
out.write_text(json.dumps(bridge,separators=(',',':'))+'\n')
print('BBM8_PAYLOAD',len(bridge['frames']),len(bridge['bones']),out)

