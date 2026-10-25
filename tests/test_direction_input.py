import subprocess,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PROBE=ROOT/'build/runtime-native/bin/Release/direction_input_test.exe'

@unittest.skipUnless(PROBE.exists(),'Build direction_input_test first')
class DirectionInputTests(unittest.TestCase):
 def test_ordered_native_direction_events(self):
  result=subprocess.run([str(PROBE)],capture_output=True,text=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
  self.assertIn('direction input PASS',result.stdout)
