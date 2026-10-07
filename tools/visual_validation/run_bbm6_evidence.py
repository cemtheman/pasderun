"""Deterministic jump strips, boundary evidence and all49 frames."""
import argparse,json,subprocess
from pathlib import Path
from PIL import Image
from run_bbm5_transfer_evidence import verified_save

def assemble(repo):
    out=repo/'build/visual_validation/BBM-6'
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
    return json.loads((out/'report.json').read_text())

def main():
    p=argparse.ArgumentParser();p.add_argument('--blender',required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[2];out=repo/'build/visual_validation/BBM-6';out.mkdir(parents=True,exist_ok=True)
    with (out/'runner.log').open('w') as log:result=subprocess.run([a.blender,'--background','--python-exit-code','1','--python',str(repo/'tools/blender/render_bbm6_jump_v1.py')],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
    report=assemble(repo)
    if result.returncode or report['machine_status']!='PASS':raise RuntimeError('Jump geometry failed; inspect report/log')
    print('Jump MACHINE_PASS; visual review required')
if __name__=='__main__':main()
