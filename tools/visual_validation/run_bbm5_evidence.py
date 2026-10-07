"""49-sample paired motion proof, full decode and fixed keyframe strips."""
import argparse,json,subprocess
from pathlib import Path
from PIL import Image,ImageDraw

def assemble(repo):
    out=repo/'build/visual_validation/BBM-5'
    for variant in ('baseline','candidate'):
        cells=out/variant;strip=Image.new('RGB',(2100,1260));frames=[];montage=Image.new('RGB',(2100,2100))
        for i in range(49):
            with Image.open(cells/'preview'/f'{i:02d}.png') as im:
                im.load();frame=im.convert('RGB');frames.append(frame.copy());montage.paste(frame.resize((300,300)),((i%7)*300,(i//7)*300))
        for col,i in enumerate((0,12,24,36,48)):
            for row,view in enumerate(('front','three_quarter','side')):
                paths=list(cells.glob(f'*_frame_{i:02d}_{view}.png'))
                if len(paths)!=1:raise RuntimeError('Missing/ambiguous keyframe')
                with Image.open(paths[0]) as im:im.load();strip.paste(im.convert('RGB'),(col*420,row*420))
        strip.save(cells/'frame_strip.png');montage.save(cells/'all_frames.png');frames[0].save(cells/'motion_preview.gif',save_all=True,append_images=frames[1:],duration=42,loop=0)
    return json.loads((out/'report.json').read_text())

def main():
    p=argparse.ArgumentParser();p.add_argument('--blender',required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[2];out=repo/'build/visual_validation/BBM-5';out.mkdir(parents=True,exist_ok=True)
    with (out/'runner.log').open('w') as log:
        for script in ('verify_bbm_body_runtime_v1.py','render_bbm5_plie_v1.py'):
            result=subprocess.run([a.blender,'--background','--python-exit-code','1','--python',str(repo/'tools/blender'/script)],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:raise RuntimeError('BBM-5 geometric proof failed; see log/report')
    report=assemble(repo)
    if report['machine_status']!='PASS':raise RuntimeError('BBM-5 machine failed')
    print('BBM-5 MACHINE_PASS; actual visual review required')
if __name__=='__main__':main()
