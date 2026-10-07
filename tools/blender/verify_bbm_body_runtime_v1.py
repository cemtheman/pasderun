"""Replay accepted BBM-4 fixtures through shared physical runtime."""
import json,sys,hashlib
from pathlib import Path
REPO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(REPO/'tools/blender'))
from bbm_body_runtime_v1 import BodyRuntime
body=BodyRuntime();prior=json.loads((REPO/'build/visual_validation/BBM-4/report.json').read_text());records={}
for label in ('flat','demi_pointe','one_leg','transitional'):
    expected=prior['fixtures']['candidate/'+label];actual=body.realize(expected['canonical_state'],expected['balance']['support_roles'],label=='demi_pointe')
    error=max(abs(actual['balance']['signed_balance_margin']-expected['balance']['signed_balance_margin']),abs(actual['contact_max_abs']-expected['contact_max_abs']),*(abs(a-b) for a,b in zip(actual['root_translation'],expected['root_translation'])))
    if error>1e-7:raise RuntimeError(f'{label}: physical extraction parity failed {error}')
    records[label]={'status':'PASS','max_metric_difference':error}
out=REPO/'build/visual_validation/BBM-5';out.mkdir(parents=True,exist_ok=True)
(out/'runtime_parity.json').write_text(json.dumps({'status':'PASS','fixtures':records,'runtime_sha256':hashlib.sha256((REPO/'tools/blender/bbm_body_runtime_v1.py').read_bytes()).hexdigest()},indent=2)+'\n')
print('Shared physical replay PASS')
