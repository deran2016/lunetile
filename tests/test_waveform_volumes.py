import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_runtime_volumes import matching_gain

class VolumeChecks(unittest.TestCase):
 def test_measured_reference(self):
  for gain in (0,.0141,.0479,.1266,.3697,1):self.assertTrue(matching_gain(gain,gain))
  self.assertTrue(matching_gain(.0141,.0138))
 def test_rejects_constant_or_linear_gain(self):
  for gain in (0,.0141,.0479,.1266,.3697):self.assertFalse(matching_gain(gain,1))
  for gain,linear in ((.0141,.01),(.0479,.25),(.1266,.50),(.3697,.75)):self.assertFalse(matching_gain(gain,linear))

if __name__=='__main__':unittest.main()
