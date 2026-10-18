import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from test_runtime_logic import equivalent,REQUIRED

class LogicComparisonTest(unittest.TestCase):
 def test_float_text_noise_does_not_hide_state_or_type_changes(self):
  self.assertEqual(len(REQUIRED),54)
  self.assertTrue(equivalent([3.6,True,1],[3.5999999999999996,True,1]))
  for right in ([3.600001,True,1],[3.6,1,1],[3.6,True,2],[3.6,True]):
   self.assertFalse(equivalent([3.6,True,1],right))

if __name__=='__main__':unittest.main()
