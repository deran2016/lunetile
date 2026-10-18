import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import verify_ci

class CIVerificationTests(unittest.TestCase):
 def setUp(self):
  root=Path(__file__).resolve().parents[1]/'build/test-ci'
  root.mkdir(parents=True,exist_ok=True)
  self.temporary=tempfile.TemporaryDirectory(dir=root)
  self.addCleanup(self.temporary.cleanup)
  self.root=Path(self.temporary.name)
  self.output=self.root/'verification'
  gate=self.root/'build/runtime-ruby-x86/patched-4.0.7/gate.json'
  gate.parent.mkdir(parents=True)
  gate.write_text('{"passed":true}',encoding='utf-8')
  self.gate=gate

 def run_checks(self,codes):
  with patch.object(verify_ci,'ROOT',self.root),patch.object(verify_ci,'inspect',return_value={'sha256':'abc'}),patch.object(verify_ci.subprocess,'check_output',return_value='commit\n'),patch.object(verify_ci.subprocess,'run',side_effect=[SimpleNamespace(returncode=n) for n in codes]):
   return verify_ci.verify(self.output)

 def test_success_records_scope_and_binary_identity(self):
  report=self.run_checks([0,0])
  self.assertTrue(report['passed'])
  self.assertEqual(report['runtime_sha256'],'abc')
  self.assertIn('no original launcher',report['scope'])
  self.assertEqual(len(report['steps']),2)

 def test_failed_check_never_produces_passed_report(self):
  with self.assertRaises(RuntimeError):self.run_checks([1])
  self.assertFalse(json.loads((self.output/'summary.json').read_text())['passed'])

 def test_failed_ruby_gate_is_rejected(self):
  self.gate.write_text('{"passed":false}',encoding='utf-8')
  with self.assertRaises(ValueError):self.run_checks([])
  self.assertFalse(json.loads((self.output/'summary.json').read_text())['passed'])

 def test_existing_output_is_not_overwritten(self):
  self.output.mkdir()
  marker=self.output/'summary.json'
  marker.write_text('preserve',encoding='utf-8')
  with self.assertRaises(FileExistsError):self.run_checks([])
  self.assertEqual(marker.read_text(),'preserve')
