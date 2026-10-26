import subprocess,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROBE=ROOT/'build/runtime-native/bin/Release/controls_state_test.exe'

class ControlsStateTests(unittest.TestCase):
 @unittest.skipUnless(PROBE.is_file(),'Native controls probe requires a build')
 def test_key_pad_validation_and_rumble_lifecycle(self):
  result=subprocess.run([str(PROBE)],capture_output=True,text=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  self.assertIn('PASS',result.stdout)
