import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'visual_validation'))
from run_bbm7_evidence import run,assemble

class PhraseEvidenceTests(unittest.TestCase):
    def test_existing_evidence_is_immutable(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'build/visual_validation/BBM-7/old';out.mkdir(parents=True)
            with patch('run_bbm7_evidence.subprocess.run') as command:
                with self.assertRaisesRegex(RuntimeError,'already exists'):run('unused',out,Path(d))
                command.assert_not_called()

    def test_old_milestone_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'isolated BBM-7'):run('unused',Path(d)/'build/visual_validation/BBM-5/new',Path(d))

    def test_numerical_fail_cannot_assemble(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'report.json').write_text(json.dumps({'machine_status':'FAIL','geometry_only':False}))
            with self.assertRaisesRegex(RuntimeError,'No rendered machine PASS'):assemble(p)
