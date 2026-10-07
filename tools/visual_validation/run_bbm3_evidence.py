"""Produce and fully decode the paired BBM-3 three-view evidence pack."""
import argparse,json,subprocess
from pathlib import Path
from PIL import Image


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--blender',required=True);args=parser.parse_args()
    repo=Path(__file__).resolve().parents[2];out=repo/'build/visual_validation/BBM-3';out.mkdir(parents=True,exist_ok=True)
    with (out/'runner.log').open('w') as log:
        result=subprocess.run([args.blender,'--background','--python-exit-code','1','--python',str(repo/'tools/blender/render_bbm3_foot_v1.py')],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
    report=json.loads((out/'report.json').read_text())
    if result.returncode or report['machine_status']!='PASS':raise RuntimeError('BBM-3 geometry failed; inspect report and runner.log')
    for variant in ('baseline','candidate'):
        sheet=Image.new('RGB',(1260,1260));detail=Image.new('RGB',(960,840))
        for row,pose in enumerate(('flat','demi_pointe','pointe_ready')):
            for col,view in enumerate(('front','three_quarter','side')):
                files=list((out/variant).glob(f'*_{pose}_{view}.png'))
                if len(files)!=1:raise RuntimeError('Missing or ambiguous evidence cell')
                with Image.open(files[0]) as cell:
                    cell.load();sheet.paste(cell.convert('RGB'),(col*420,row*420));detail.paste(cell.crop((125,280,285,420)).resize((320,280)),(col*320,row*280))
        sheet.save(out/variant/'contact.png');detail.save(out/variant/'foot_detail.png')
    if result.returncode or report['machine_status']!='PASS':raise RuntimeError('BBM-3 geometry failed; inspect report')
    print('BBM-3 MACHINE_PASS; actual visual review required')

if __name__=='__main__':main()
