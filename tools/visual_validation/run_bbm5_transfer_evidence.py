"""Fully decoded 25-sample supported weight-transfer evidence."""
import argparse,json,subprocess,io,os
from pathlib import Path
from PIL import Image

def verified_save(image,path):
    data=io.BytesIO();image.save(data,format='PNG');payload=data.getvalue()
    with path.open('wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
    with Image.open(path) as decoded:decoded.load()

def assemble(repo):
    out=repo/'build/visual_validation/BBM-5/weight-transfer'
    for variant in ('baseline','candidate'):
        cells=out/variant;strip=Image.new('RGB',(2100,1260));montage=Image.new('RGB',(2100,2100));frames=[]
        for i in range(25):
            with Image.open(cells/'preview'/f'{i:02d}.png') as im:im.load();frame=im.convert('RGB');frames.append(frame.copy());montage.paste(frame,((i%5)*420,(i//5)*420))
        for col,i in enumerate((0,6,12,18,24)):
            for row,view in enumerate(('front','three_quarter','side')):
                files=list(cells.glob(f'*_frame_{i:02d}_{view}.png'))
                if len(files)!=1:raise RuntimeError('Missing/ambiguous transfer keyframe')
                with Image.open(files[0]) as im:im.load();strip.paste(im.convert('RGB'),(col*420,row*420))
        verified_save(strip,cells/'frame_strip.png');verified_save(strip.resize((1050,630)),cells/'review_strip.png');verified_save(montage,cells/'all_frames.png');frames[0].save(cells/'motion_preview.gif',save_all=True,append_images=frames[1:],duration=83,loop=0)
    return json.loads((out/'report.json').read_text())

def main():
    p=argparse.ArgumentParser();p.add_argument('--blender',required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[2];out=repo/'build/visual_validation/BBM-5/weight-transfer';out.mkdir(parents=True,exist_ok=True)
    with (out/'runner.log').open('w') as log:result=subprocess.run([a.blender,'--background','--python-exit-code','1','--python',str(repo/'tools/blender/render_bbm5_weight_transfer_v1.py')],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
    report=assemble(repo)
    if result.returncode or report['machine_status']!='PASS':raise RuntimeError('Weight-transfer geometry failed; inspect report/log')
    print('Transfer MACHINE_PASS; visual review required')
if __name__=='__main__':main()
