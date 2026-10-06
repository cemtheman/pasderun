"""Regenerate the unmodified Phase 10.6.8 baseline on Linux or Windows.

Delegates to existing authorities. Fails closed; never chooses a visual verdict.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--blender', required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    out = repo / 'build/visual_validation/BBM-0/baseline'
    out.mkdir(parents=True, exist_ok=True)
    profiles = repo / 'build/phase10_6'
    profiles.mkdir(parents=True, exist_ok=True)
    source = repo / 'assets/characters/low_poly_girl/low_poly_girl .glb'
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    original = digest(source)
    asset = repo / 'assets/ballet_motion'
    names = {
        'calibration': 'ballet_rig', 'canonical': 'canonical_ballet',
        'constraints': 'anatomical_constraint', 'grammar': 'ballet_pose_grammar',
        'poses': 'canonical_pose_solver', 'retarget': 'calibrated_rig_retarget',
    }
    p = {key: profiles / ('low_poly_girl_' + value + '_profile_v1.json')
         for key, value in names.items()}
    p['poses'] = profiles / 'low_poly_girl_canonical_pose_solver_v1.json'
    p['retarget'] = profiles / 'low_poly_girl_calibrated_rig_retarget_v1.json'
    def run(command, label):
        with (out / (label + '.log')).open('w') as log:
            result = subprocess.run([str(v) for v in command], cwd=repo,
                                    stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f'{label} failed ({result.returncode}); see {out / (label + ".log")}')
    def blender(script, flags, label):
        run([args.blender, '--background', '--python-exit-code', '1', '--python',
             repo / 'tools/blender' / script, '--', *flags], label)
    blender('build_ballet_rig_calibration_v1.py', ['--repo', repo, '--seed',
        source.parent / 'ballet_rig_calibration_seed_v1.json', '--output', p['calibration']], '01-calibration')
    commands = [
        ('build_canonical_ballet_profile_v1.py', ['--repo', repo, '--calibration', p['calibration'], '--spec', asset / 'canonical_ballet_skeleton_v1.json', '--output', p['canonical']]),
        ('build_anatomical_constraint_profile_v1.py', ['--canonical-profile', p['canonical'], '--canonical-spec', asset / 'canonical_ballet_skeleton_v1.json', '--constraints', asset / 'anatomical_constraints_v1.json', '--output', p['constraints']]),
        ('build_ballet_pose_grammar_profile_v1.py', ['--canonical-profile', p['canonical'], '--constraint-profile', p['constraints'], '--grammar', asset / 'ballet_pose_grammar_v1.json', '--fixtures', asset / 'ballet_pose_fixtures_v1.json', '--output', p['grammar']]),
        ('build_canonical_pose_solver_v1.py', ['--canonical-profile', p['canonical'], '--constraint-profile', p['constraints'], '--grammar-profile', p['grammar'], '--intents', asset / 'foundation_pose_intents_v1.json', '--output', p['poses']]),
        ('build_calibrated_rig_retarget_v1.py', ['--canonical-profile', p['canonical'], '--constraint-profile', p['constraints'], '--pose-profile', p['poses'], '--axis-contract', asset / 'retarget_axis_contract_v1.json', '--output', p['retarget']]),
    ]
    for index, (script, flags) in enumerate(commands, 2):
        run([sys.executable, repo / 'tools/ballet_motion' / script, *flags], f'{index:02d}-{script}')
    flags = ['--repo', repo, '--canonical-profile', p['canonical'], '--constraint-profile', p['constraints'], '--retarget-profile', p['retarget'], '--retarget-axis-contract', asset / 'retarget_axis_contract_v1.json', '--grammar-profile', p['grammar'], '--intent-spec', asset / 'foundation_pose_intents_v1.json', '--static-contract', asset / 'static_rig_application_contract_v1.json', '--visual-contract', asset / 'foundation_pose_visual_gate_v1.json', '--output', out / 'contact.png', '--report', out / 'geometry_report.json']
    blender('render_foundation_pose_visual_gate_v1.py', flags, '07-render')
    if digest(source) != original:
        raise RuntimeError('Source GLB changed')
    report = json.loads((out / 'geometry_report.json').read_text())
    for key in ['static_realization_pass', 'mesh_contact_pass', 'upper_body_hand_axial_continuity_pass', 'hand_mesh_centerline_spacing_pass', 'hand_mesh_retarget_wrist_seed_preserved_pass', 'hand_mesh_runtime_clearance_solver_pass', 'ballet_hand_shape_applied', 'render_count_pass']:
        if report['automated_gate'].get(key) is not True:
            raise RuntimeError(f'Gate failed: {key}')
    if report['render_count'] != 18:
        raise RuntimeError('Expected 18 renders')
    manifest = {'git_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(), 'source_glb_sha256': original, 'profiles_sha256': {k: digest(v) for k, v in p.items()}, 'render_report_sha256': digest(out / 'geometry_report.json'), 'machine_status': 'PASS', 'ai_visual_status': 'NOT_REVIEWED'}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('BBM-0 MACHINE_PASS; actual image inspection still required')


if __name__ == '__main__':
    main()
