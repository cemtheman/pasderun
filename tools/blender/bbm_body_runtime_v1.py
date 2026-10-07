"""Isolated observed support/geometry-COM proof; existing rig and contacts."""
import copy,json,sys,math,hashlib,subprocess,statistics
from pathlib import Path
import bpy
from mathutils import Vector,Quaternion,Matrix
REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'tools/blender'),str(REPO/'tools/ballet_motion')]
import render_foundation_pose_visual_gate_v1 as gate
from render_bbm3_foot_v1 import apply_calibrated_basis
from distributed_turnout_v1 import derive_turnout,alignment_diagnostics
from support_balance_v1 import balance_diagnostics
from foot_semantics_v1 import anatomical_plantar_from_canonical,foot_state
from calibrated_rig_retarget import retarget_pose_solution
from canonical_pose_solver import _check_preferred_joint_envelope
from ballet_pose_validators import validate_pose


def surface_centroid(rig):
    """Uniform surface density, including costume/hair; explicitly a proxy."""
    graph=bpy.context.evaluated_depsgraph_get();inv=rig.matrix_world.inverted();weighted=Vector();area=0.
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or not any(m.type=='ARMATURE' and m.object==rig for m in obj.modifiers):continue
        evaluated=obj.evaluated_get(graph);mesh=evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles();transform=inv@evaluated.matrix_world
            vertices=[transform@v.co for v in mesh.vertices]
            for tri in mesh.loop_triangles:
                a,b,c=[vertices[i] for i in tri.vertices];weight=(b-a).cross(c-a).length*.5
                weighted+=(a+b+c)*(weight/3);area+=weight
        finally:evaluated.to_mesh_clear()
    if area<=0:raise RuntimeError('No observed surface area')
    return weighted/area,area


class BodyRuntime:
    def __init__(self):
        load=lambda p:json.loads(p.read_text());base=REPO/'build/phase10_6';asset=REPO/'assets/ballet_motion'
        self.canonical=load(base/'low_poly_girl_canonical_ballet_profile_v1.json');self.constraints=load(base/'low_poly_girl_anatomical_constraint_profile_v1.json');self.axis=load(asset/'retarget_axis_contract_v1.json');self.static=load(asset/'static_rig_application_contract_v1.json');self.visual=load(asset/'foundation_pose_visual_gate_v1.json');self.grammar=load(base/'low_poly_girl_ballet_pose_grammar_profile_v1.json');self.prior=load(REPO/'build/visual_validation/BBM-3/report.json')
        source=REPO/self.canonical['source']['path']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=self.canonical['source']['sha256']:raise RuntimeError('Source changed')
        bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(source));self.rig=gate.static_core.find_armature(self.canonical['source']['armature'])
        for obj in bpy.context.scene.objects:
            if obj.animation_data:obj.animation_data_clear()
        self.runtime=gate.prepare_contact_runtime(self.rig,self.canonical,self.static);axes=self.canonical['body_frame']['declared_axes_armature_local'];self.up=Vector(axes['up']);self.front=Vector(axes['front']);self.left=Vector(axes['left']);self.q=float(self.runtime['sampling']['low_height_quantile']);self.neutral=self.prior['ankle_neutral_offset_deg']
        self.scene=bpy.context.scene;gate.configure_workbench(self.scene,420);self.camera,self.center,self.scale=gate.create_camera(self.rig,self.canonical)
        self.upper=load(REPO/'build/visual_validation/BBM-1/elbow-path/report.json')['samples'][0]['orientations_wxyz']

    def realize(self,state,roles,demi=False):
        rig=self.rig;canonical=self.canonical;constraints=self.constraints;axis=self.axis;static=self.static;grammar=self.grammar;runtime=self.runtime;up=self.up;front=self.front;left=self.left;q=self.q;neutral=self.neutral;upper=self.upper
        active=[s for s,r in roles.items() if r=='SUPPORT'];regions=('fore',) if demi else ('rear','fore')
        violations=_check_preferred_joint_envelope(state,constraints)
        if violations:raise RuntimeError(str(violations))
        sol={'pose':'bbm_physical','state':state,'validation':validate_pose(state,grammar['poses']['bras_bas'],constraints,canonical)}
        entry=retarget_pose_solution(sol,canonical,constraints,axis);gate.static_core.apply_rotation_deltas(rig,entry)
        for bone in rig.pose.bones:
            matrix=bone.matrix_basis.copy();rotation=matrix.to_quaternion().normalized().to_matrix().to_4x4();rotation.translation=matrix.translation;bone.matrix_basis=rotation
        bpy.context.view_layer.update();proof={}
        for side in active:
            foot=canonical['canonical_bones'][f'{side}_foot'];toe=canonical['canonical_bones'][f'{side}_toes']
            if not demi:
                th=static['proof_thresholds'];result=gate.static_core.solve_preferred_ankle_flat_contact(rig,canonical,constraints,f'{side}_foot',side,up,runtime['anchors'],runtime['rest_heights'],q,th['full_foot_seed_up_alignment_min_dot'],th['full_foot_mesh_search_coarse_step_deg'],th['full_foot_mesh_search_refine_steps_deg']);desired=result['basis'];raw=result['plantar_dorsiflexion'];inversion=result['inversion_eversion']
            else:
                parent,rest=gate.static_core.canonical_parent_and_rest_local(rig,canonical,f'{side}_foot');raw=neutral[side]+35;inversion=0;desired=(parent@rest@Matrix.Rotation(math.radians(-raw),3,'X')).to_quaternion().normalized().to_matrix()
            apply_calibrated_basis(rig,foot['rig_bone'],gate.static_core.rig_basis_from_canonical_pose(foot,desired))
            observed=gate.static_core.canonical_basis_from_rig_pose(rig.pose.bones[foot['rig_bone']],foot);error=gate.matrix_max_error(observed,desired)
            decoded=anatomical_plantar_from_canonical(constraints,round(raw,3),neutral[side]);foot_state(constraints,'DEMI_POINTE' if demi else 'FLAT',decoded['anatomical_plantar_deg'],35 if demi else 0,inversion)
            parent,rest=gate.static_core.canonical_parent_and_rest_local(rig,canonical,f'{side}_toes');toe_target=(parent@rest@Matrix.Rotation(math.radians(35 if demi else 0),3,'X')).to_quaternion().normalized().to_matrix();apply_calibrated_basis(rig,toe['rig_bone'],gate.static_core.rig_basis_from_canonical_pose(toe,toe_target));toe_error=gate.matrix_max_error(gate.static_core.canonical_basis_from_rig_pose(rig.pose.bones[toe['rig_bone']],toe),toe_target)
            if decoded['status']!='PASS' or max(error,toe_error)>axis['thresholds']['hierarchy_reconstruction_max_error']:raise RuntimeError('Unchanged anatomical/matrix gate failed')
            proof[side]={'anatomical':decoded,'foot_matrix_error':error,'toe_matrix_error':toe_error,'inversion_eversion_deg':inversion}
        heights=gate.static_core.contact_heights(rig,runtime['anchors'],up,q);shift=statistics.median(runtime['rest_heights'][s][r]-heights[s][r] for s in active for r in regions);gate.static_core.set_root_translation_armature_space(rig,canonical['canonical_bones']['pelvis']['rig_bone'],up*shift)
        for name in ('Chest','Clavicle_L','Clavicle_R','Upper_Arm_L','Upper_Arm_R','Lower_Arm_L','Lower_Arm_R','Hand_L','Hand_R','Head'):gate.static_core.apply_absolute_rig_rotation_via_matrix_basis(rig,name,Quaternion(upper[name]).to_matrix())
        gate.static_core.apply_ballet_hand_shape(rig,canonical,static)
        heights=gate.static_core.contact_heights(rig,runtime['anchors'],up,q);errors={s:{r:heights[s][r]-runtime['rest_heights'][s][r] for r in regions} for s in active};maximum=max(abs(e) for v in errors.values() for e in v.values())
        if maximum>runtime['contact_tolerance']:raise RuntimeError('Unchanged support contact tolerance failed')
        points={};centers={}
        for side in ('left','right'):
            selected=[]
            for region in regions:
                ps=sorted(gate.static_core.evaluated_sample_points(rig,runtime['anchors'][side][region]),key=lambda p:p.dot(up));selected+=ps[:max(3,int(len(ps)*q))]
            points[side]=[(p.dot(left),p.dot(front)) for p in selected];centers[side]=[sum(p[i] for p in points[side])/len(points[side]) for i in (0,1)]
        com,area=surface_centroid(rig);balance=balance_diagnostics(points,(com.dot(left),com.dot(front)),roles)
        result={'balance':balance,'surface_area':area,'surface_centroid_armature':list(com),'contact_errors':errors,'contact_max_abs':maximum,'root_translation':list(up*shift),'support_centers':centers,'support_area_sampling':'lowest contact-policy quantile (0.1), minimum3 vertices per declared region; practical geometry proxy','foot_proof':proof,'heights':heights}
        alignment={}
        for side in active:
            shin=canonical['canonical_bones'][f'{side}_shin'];toe=canonical['canonical_bones'][f'{side}_toes'];heading=gate.static_core.canonical_basis_from_rig_pose(rig.pose.bones[shin['rig_bone']],shin).col[2];ray=rig.pose.bones[toe['rig_bone']].tail-rig.pose.bones[toe['rig_bone']].head;alignment[side]=alignment_diagnostics(constraints,list(heading),list(ray),list(front),list(up))
        root=rig.pose.bones[canonical['canonical_bones']['pelvis']['rig_bone']];drift=root.head-root.bone.head_local;horizontal=[drift.dot(left),drift.dot(front)]
        if max(abs(v) for v in horizontal)>1e-7:raise RuntimeError('Observed horizontal root drift')
        result.update({'alignment':alignment,'observed_root_horizontal_offset':horizontal,'wrist':gate.validate_hand_axial_continuity(rig,canonical,constraints,self.visual)})
        return result
