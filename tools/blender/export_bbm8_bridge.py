"""Retarget immutable BBM-7 measured poses; no prior solve/render/validation."""
import bpy,json,sys,hashlib
from pathlib import Path
from mathutils import Matrix,Quaternion,Vector
ROOT=Path(__file__).resolve().parents[2]
def normalized(n):return n.replace('_','').replace(' ','').lower()
def main():
    source=ROOT/'assets/characters/low_poly_girl/low_poly_girl .glb'
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
    imported=json.loads((ROOT/'build/visual_validation/BBM-8/environment-probe/import_rest.json').read_text())
    report_path=ROOT/'build/visual_validation/BBM-7/candidate-01/report.json'
    report=json.loads(report_path.read_text())
    c=Matrix(((1,0,0),(0,0,1),(0,-1,0)))
    lookup={normalized(b.name):b for b in rig.data.bones}

    records=[];frames=[]
    for b in imported['bones']:
        rest=b['rest'];g=Matrix(rest[:3]).transposed();bone=lookup['hat' if normalized(b['name'])=='hat2' else normalized(b['name'])]
        records.append({'name':b['name'],'blender_name':bone.name,'parent':b['parent'],
                        'blender_rest': [list(row) for row in bone.matrix_local],
                        'godot_rest':rest,'rest_head_error':(c@bone.head_local-Vector(rest[3])).length,
                        'right_bind': [list(row) for row in bone.matrix_local.to_3x3().inverted()@c.inverted()@g]})
    for key,row in report['samples'].items():
        if not key.startswith('clear/'):continue
        rotations={n:Quaternion(q).to_matrix() for n,q in row['orientations_wxyz'].items()};positions={}
        payload=[]
        for r in records:
            b=rig.data.bones[r['blender_name']]
            if b.parent is None:pos=b.head_local+Vector(row['root_translation'])
            else:
                parent=b.parent
                pos=positions[parent.name]+rotations[parent.name]@parent.matrix_local.to_3x3().inverted()@(b.head_local-parent.head_local)
            positions[b.name]=pos
            q=(c@rotations[b.name]@Matrix(r['right_bind'])).to_quaternion().normalized()
            v=c@pos;payload.append([q.x,q.y,q.z,q.w,v.x,v.y,v.z])
        frames.append({'time':row['time'],'poses':payload,'intent':row['intent']})
    out=ROOT/'build/visual_validation/BBM-8/environment-probe/bridge_candidate.json'
    out.write_text(json.dumps({'schema':1,'status':'UNVERIFIED_RUNTIME_CANDIDATE','duration':6.,'source_glb_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'accepted_report_sha256':hashlib.sha256(report_path.read_bytes()).hexdigest(),'bones':records,'frames':frames},separators=(',',':'))+'\n')
    print('BBM8 bridge',len(records),len(frames),out)
if __name__=='__main__':main()
