"""Deterministic jump strips, boundary evidence and all49 frames."""
import argparse,json,subprocess,hashlib
from pathlib import Path
from PIL import Image
from run_bbm5_transfer_evidence import verified_save

def assemble(repo,out=None):
    out=out or repo/'build/visual_validation/BBM-6/candidate-01'
    for variant in ('baseline','candidate'):
        cells=out/variant;frames=[];montage=Image.new('RGB',(2100,2100))
        for i in range(49):
            with Image.open(cells/'preview'/f'{i:02d}.png') as im:im.load();frame=im.convert('RGB');frames.append(frame.copy());montage.paste(frame.resize((300,300)),((i%7)*300,(i//7)*300))
        for name,indices in [('frame_strip',(0,12,24,36,48)),('contact_boundaries',(16,17,26,27))]:
            strip=Image.new('RGB',(420*len(indices),1260))
            for col,i in enumerate(indices):
                for row,view in enumerate(('front','three_quarter','side')):
                    files=list(cells.glob(f'*_frame_{i:02d}_{view}.png'))
                    if len(files)!=1:raise RuntimeError('Missing/ambiguous keyframe')
                    with Image.open(files[0]) as im:im.load();strip.paste(im.convert('RGB'),(col*420,row*420))
            verified_save(strip,cells/f'{name}.png');verified_save(strip.resize((210*len(indices),630)),cells/f'{name}_review.png')
        verified_save(montage,cells/'all_frames.png');frames[0].save(cells/'motion_preview.gif',save_all=True,append_images=frames[1:],duration=42,loop=0)
        with Image.open(cells/'motion_preview.gif') as gif:
            if gif.n_frames!=49:raise RuntimeError('Incomplete motion preview')
            for i in range(gif.n_frames):gif.seek(i);gif.load()
    return json.loads((out/'report.json').read_text())

def main():
    p=argparse.ArgumentParser();p.add_argument('--blender',required=True);p.add_argument('--output',type=Path);a=p.parse_args();repo=Path(__file__).resolve().parents[2];out=(a.output or repo/'build/visual_validation/BBM-6/candidate-01').resolve()
    if out.exists():raise RuntimeError('Evidence directory already exists; use a fresh candidate output')
    out.mkdir(parents=True)
    with (out/'runner.log').open('w') as log:result=subprocess.run([a.blender,'--background','--python-exit-code','1','--python',str(repo/'tools/blender/render_bbm6_jump_v1.py'),'--','--output',str(out)],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
    if result.returncode:
        (out/'execution_failure.json').write_text(json.dumps({'machine_status':'FAIL','returncode':result.returncode,'ai_visual_status':'NOT_REVIEWED'})+'\n')
        raise RuntimeError('Jump execution failed; inspect runner.log; no evidence assembled')
    report=json.loads((out/'report.json').read_text())
    if report['machine_status']!='PASS':raise RuntimeError('Jump geometry failed; inspect report/log')
    assemble(repo,out)
    manifest={'machine_status':'PASS','ai_visual_status':'NOT_REVIEWED','files_sha256':{str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.rglob('*')) if f.is_file()},'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Jump MACHINE_PASS; visual review required')
if __name__=='__main__':main()
