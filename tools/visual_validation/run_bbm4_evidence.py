"""Render/decode BBM-4 paired static fixtures; require independent review."""
import argparse,json,subprocess
from pathlib import Path
from PIL import Image,ImageDraw

POSES=('flat','demi_pointe','one_leg','transitional')
def assemble(repo):
    out=repo/'build/visual_validation/BBM-4';report=json.loads((out/'report.json').read_text())
    for variant in ('baseline','candidate'):
        sheet=Image.new('RGB',(1260,1680))
        for row,pose in enumerate(POSES):
            for col,view in enumerate(('front','three_quarter','side')):
                files=list((out/variant).glob(f'*_{pose}_{view}.png'))
                if len(files)!=1:raise RuntimeError('Missing/ambiguous rendered cell')
                with Image.open(files[0]) as cell:
                    cell.load()
                    if cell.size!=(420,420):raise RuntimeError('Inconsistent framing')
                    sheet.paste(cell.convert('RGB'),(col*420,row*420))
        sheet.save(out/variant/'contact.png')
    chart=Image.new('RGB',(1000,400),'white');draw=ImageDraw.Draw(chart)
    for i,pose in enumerate(POSES):
        b=report['fixtures']['candidate/'+pose]['balance'];origin=(i*250+125,220)
        convert=lambda p:(origin[0]+p[0]*650,origin[1]-p[1]*650)
        hull=[convert(p) for p in b['support_polygon']];draw.polygon(hull,fill='#d7e9df',outline='#20533b')
        x,y=convert(b['projected_com_proxy']);draw.ellipse((x-4,y-4,x+4,y+4),fill='#bf302d')
        draw.text((i*250+10,20),pose,fill='black');draw.text((i*250+10,40),f"margin {b['signed_balance_margin']:.5f}",fill='black')
    draw.text((10,370),'Body LEFT horizontal / FRONT vertical. Red: surface-density COM proxy; green: observed support proxy.',fill='black');chart.save(out/'support_proxy.png')
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--blender',required=True);a=p.parse_args();repo=Path(__file__).resolve().parents[2];out=repo/'build/visual_validation/BBM-4';out.mkdir(parents=True,exist_ok=True)
    with (out/'runner.log').open('w') as log:
        result=subprocess.run([a.blender,'--background','--python-exit-code','1','--python',str(repo/'tools/blender/render_bbm4_support_v1.py')],cwd=repo,stdout=log,stderr=subprocess.STDOUT)
    report=assemble(repo)
    if result.returncode or report['machine_status']!='PASS':raise RuntimeError('BBM-4 geometry failed; see report/log')
    print('BBM-4 MACHINE_PASS; visual review required')
if __name__=='__main__':main()
