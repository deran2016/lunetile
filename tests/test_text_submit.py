import subprocess,unittest
from pathlib import Path
PROBE=Path(__file__).resolve().parents[1]/'build/runtime-native/bin/Release/text_submit_test.exe'
@unittest.skipUnless(PROBE.exists(),'Build text_submit_test first')
class TextSubmitTests(unittest.TestCase):
 def test_native_submit_commits_then_delivers_once(self):
  r=subprocess.run([str(PROBE)],capture_output=True,text=True,timeout=10)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
  self.assertIn('text submit PASS',r.stdout)
