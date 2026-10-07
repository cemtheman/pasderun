"""Independent fore/rear footprint audit of accepted plié sampled states."""
import sys,json,math,hashlib
from pathlib import Path
from mathutils import Vector
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO/'tools/blender'))
from bbm_body_runtime_v1 import BodyRuntime,gate
body=BodyRuntime();path=REPO/'build/visual_validation/BBM-5/report.json';prior=json.loads(path.read_text());reference=None;records={};failures=[];bound=body.runtime['metrics']['foot_chain_length']*.05
for i in range(49):
    sample=prior['samples'][f'candidate/{i:02d}'];body.realize(sample['canonical_state'],{'left':'SUPPORT','right':'SUPPORT'});points={}
    for s in ('left','right'):
        for region in ('rear','fore'):
            ps=gate.static_core.evaluated_sample_points(body.rig,body.runtime['anchors'][s][region]);points[s+'/'+region]=sum(ps,Vector())/len(ps)
    if reference is None:reference={k:v.copy() for k,v in points.items()}
    drift={k:math.hypot((v-reference[k]).dot(body.left),(v-reference[k]).dot(body.front)) for k,v in points.items()}
    records[str(i)]=drift
    if max(drift.values())>bound:failures.append({'frame':i,'gate':'fore_rear_horizontal_drift','values':drift})
out=path.parent/'footprint_audit.json';out.write_text(json.dumps({'machine_status':'FAIL' if failures else 'PASS','failures':failures,'samples':records,'bound_foot_chain_fraction':.05,'bound':bound,'plie_report_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')
if failures:raise RuntimeError(str(failures))
print('Independent full footprint audit PASS')
