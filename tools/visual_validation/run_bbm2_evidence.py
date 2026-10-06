"""Produce and fully decode the paired BBM-2 three-view evidence pack."""
import argparse,json,subprocess
from pathlib import Path
from PIL import Image


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--blender',required=True);args=parser.parse_args()
    repo=Path(__file__).resolve().parents[2];out=repo/'build/visual_validation/BBM-2';out.mkdir(parents=True,exist_ok=True)
    with (out/'runner.log').open('w') as log:
        result=subprocess.run([args.blender,'--background','--python-exit-code','1','--python',str(repo/'tools/blender/render_bbm2_alignment_v1.py')],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
    report=json.loads((out/'report.json').read_text())
    for variant in ('baseline','candidate'):
        sheet=Image.new('RGB',(1260,1260))
        for row,pose in enumerate(('first','fifth','plie')):
            for col,view in enumerate(('front','three_quarter','side')):
                files=list((out/variant).glob(f'*_{pose}_{view}.png'))
                if len(files)!=1:raise RuntimeError('Missing or ambiguous evidence cell')
                with Image.open(files[0]) as cell:
                    cell.load();sheet.paste(cell.convert('RGB'),(col*420,row*420))
        sheet.save(out/variant/'contact.png')
    if result.returncode or report['machine_status']!='PASS':raise RuntimeError('BBM-2 geometry failed; inspect report')
    print('BBM-2 MACHINE_PASS; actual visual review required')

if __name__=='__main__':main()
