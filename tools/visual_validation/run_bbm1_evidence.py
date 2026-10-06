"""Run BBM-1 experiments, decode every image, and assemble review artifacts.

A successful render is not an AI visual PASS. Historical replay is explicitly
MACHINE_FAIL diagnostic evidence; failed experiments cannot become active assets.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--blender',required=True)
    parser.add_argument('--variant',choices=('historical-diagnostic','candidate','opening-hand-line'),default='candidate')
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[2]
    out=repo/'build/visual_validation/BBM-1'/args.variant
    out.mkdir(parents=True,exist_ok=True)
    command=[args.blender,'--background','--python-exit-code','1','--python',str(repo/'tools/blender/render_bbm1_upper_body_v1.py'),'--','--output',str(out)]
    if args.variant=='historical-diagnostic':command+=['--wrist-mode','historical','--diagnostic-render']
    else:
        command+=['--wrist-mode','coordinated','--hand-shape','--phrase-coordination','--preview']
        if args.variant=='opening-hand-line':command+=['--hand-line']
    with (out/'runner.log').open('w') as log:
        result=subprocess.run(command,cwd=repo,stdout=log,stderr=subprocess.STDOUT)
    report=json.loads((out/'report.json').read_text())
    if args.variant!='historical-diagnostic' and (result.returncode or report['machine_status']!='PASS'):
        raise RuntimeError(f'Geometry failed; see {out / "report.json"}')
    if args.variant=='historical-diagnostic' and report['machine_status']!='FAIL':
        raise RuntimeError('Historical diagnostic must preserve its failed gate status')
    sheet=Image.new('RGB',(1260,2100))
    for row,frame in enumerate((1,13,25,37,49)):
        for col,view in enumerate(('front','three_quarter','side')):
            paths=list(out.glob(f'*frame_{frame:02d}_{view}.png'))
            if len(paths)!=1:raise RuntimeError('Missing or ambiguous deterministic cell')
            with Image.open(paths[0]) as image:sheet.paste(image.convert('RGB'),(col*420,row*420))
    if args.variant=='historical-diagnostic':
        ImageDraw.Draw(sheet).text((10,10),'HISTORICAL DIAGNOSTIC: MACHINE_FAIL (wrist gate)',fill='red')
    sheet.save(out/'verified_frame_strip.png')
    if args.variant!='historical-diagnostic':
        frames=[Image.open(p).convert('RGB') for p in sorted((out/'preview_frames').glob('*.png'))]
        if len(frames)!=49:raise RuntimeError('Preview grid incomplete')
        frames[0].save(out/'motion_preview.gif',save_all=True,append_images=frames[1:],duration=42,loop=0)
        montage=Image.new('RGB',(1680,1260))
        for i,index in enumerate(range(28,40)):montage.paste(frames[index],((i%4)*420,(i//4)*420))
        montage.save(out/'opening_continuity_29_40.png')
    print(f"{args.variant}: {report['machine_status']}; AI visual review is separate")


if __name__=='__main__':main()
