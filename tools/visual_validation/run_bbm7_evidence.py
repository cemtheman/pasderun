"""Fresh-only BBM-7 evidence; never assemble a failed execution as PASS."""
import argparse,hashlib,json,subprocess,math
from pathlib import Path
from PIL import Image,ImageDraw
from run_bbm5_transfer_evidence import verified_save

def assemble(out):
    report=json.loads((out/'report.json').read_text())
    if report['machine_status']!='PASS' or report['geometry_only']:
        raise RuntimeError('No rendered machine PASS; refuse assembly')
    times=report['times'];count=len(times);keys=report['keyframe_indices']
    for style in {k.split('/')[0] for k in report['samples']}:
        cells=out/style;frames=[]
        for i in range(count):
            with Image.open(cells/'preview'/f'{i:03d}.png') as im:im.load();frames.append(im.convert('RGB').copy())
        for panel,start in enumerate(range(0,count,28)):
            indices=range(start,min(start+28,count));montage=Image.new('RGB',(1680,480*math.ceil(len(indices)/7)),(245,245,245))
            draw=ImageDraw.Draw(montage)
            for local,i in enumerate(indices):
                x=(local%7)*240;y=(local//7)*480
                montage.paste(frames[i].resize((240,240)),(x,y))
                record=report['samples'][f'{style}/{i:03d}']
                draw.text((x+4,y+247),f'{i:03d}  t={times[i]:.6f}\n{record["intent"]["primitive"]}',fill='black')
            verified_save(montage,cells/f'temporal_panel_{panel:02d}.png')
        strip=Image.new('RGB',(420*len(keys),1260))
        for col,i in enumerate(keys):
            for row,view in enumerate(('front','three_quarter','side')):
                matches=list(cells.glob(f'*_frame_{i:03d}_{view}.png'))
                if len(matches)!=1:raise RuntimeError('Missing/ambiguous multi-angle frame')
                with Image.open(matches[0]) as im:im.load();strip.paste(im.convert('RGB'),(col*420,row*420))
        verified_save(strip,cells/'key_strip.png')
        verified_save(strip.resize((210*len(keys),630)),cells/'key_strip_review.png')
        selected=[frames[min(range(count),key=lambda j:abs(times[j]-i/72))] for i in range(73)]
        duration=round(report['samples'][f'{style}/000']['intent']['duration_seconds']*1000/72)
        selected[0].save(cells/'motion_preview.gif',save_all=True,append_images=selected[1:],duration=duration,loop=0)
    decoded=0
    for f in out.rglob('*'):
        if f.suffix in ('.png','.gif'):
            with Image.open(f) as im:
                for i in range(getattr(im,'n_frames',1)):im.seek(i);im.load()
            decoded+=1
    manifest={'machine_status':'PASS','ai_visual_status':'NOT_REVIEWED','decoded_images':decoded,
              'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'files_sha256':{str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.rglob('*')) if f.is_file()}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return report

def run(blender,output,repo):
    if output.exists():raise RuntimeError('Evidence already exists; choose fresh output')
    if not output.resolve().is_relative_to((repo/'build/visual_validation/BBM-7').resolve()):
        raise RuntimeError('Output must be an isolated BBM-7 evidence path')
    output.parent.mkdir(parents=True,exist_ok=True)
    log=output.with_suffix('.runner.log')
    with log.open('w') as f:
        result=subprocess.run([blender,'--background','--python-exit-code','1','--python',str(repo/'tools/blender/render_bbm7_phrase_v1.py'),'--','--output',str(output)],cwd=repo,stdout=f,stderr=subprocess.STDOUT)
    if result.returncode:raise RuntimeError('BBM-7 execution failed; inspect runner log; no assembly')
    return assemble(output)

def main():
    p=argparse.ArgumentParser();p.add_argument('--blender',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    run(a.blender,a.output.resolve(),Path(__file__).resolve().parents[2])
    print('BBM-7 MACHINE_PASS; actual whole-phrase visual review required')
if __name__=='__main__':main()
