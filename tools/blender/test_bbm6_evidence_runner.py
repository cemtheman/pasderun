"""Execution failure must never assemble or promote stale jump evidence."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'visual_validation'))
import run_bbm6_evidence as runner

class JumpEvidenceFailureTests(unittest.TestCase):
    def test_failed_renderer_does_not_assemble_even_with_pass_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'new'
            def failed(*args, **kwargs):
                (out/'report.json').write_text(json.dumps({'machine_status':'PASS'}))
                return type('Result',(),{'returncode':1})()
            with patch.object(sys,'argv',['runner','--blender','unused','--output',str(out)]), patch.object(runner.subprocess,'run',side_effect=failed), patch.object(runner,'assemble') as assemble:
                with self.assertRaisesRegex(RuntimeError,'execution failed'):runner.main()
                assemble.assert_not_called()
            self.assertEqual(json.loads((out/'execution_failure.json').read_text())['machine_status'],'FAIL')
            self.assertFalse((out/'manifest.json').exists())

    def test_existing_evidence_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);marker=out/'accepted.txt';marker.write_text('keep')
            with patch.object(sys,'argv',['runner','--blender','unused','--output',str(out)]), patch.object(runner.subprocess,'run') as run:
                with self.assertRaisesRegex(RuntimeError,'already exists'):runner.main()
                run.assert_not_called()
            self.assertEqual(marker.read_text(),'keep')
