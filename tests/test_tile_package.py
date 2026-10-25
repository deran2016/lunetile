import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from package_tile_client import validate

class TilePackageTests(unittest.TestCase):
 def test_rejects_unverified_or_unmeasured_dll(self):
  with self.assertRaisesRegex(ValueError,'verification'):validate({'passed':False},{},{})
  verification={'passed':True,'artifacts':{'xp':{'sha256':'verified'}}}
  reports={'xp':{'hashes':{'xp':{'candidate':'measured'}}}}
  with self.assertRaisesRegex(ValueError,'DLL differs'):validate(verification,reports,{'xp':{'sha256':'other'}})
 def test_rejects_empty_performance_report(self):
  verification={'passed':True,'artifacts':{'xp':{'sha256':'same'}}}
  report={'passed':True,'profile':'xp-tile-cache','hashes':{'xp':{'candidate':'same'}},'results':[]}
  with self.assertRaisesRegex(ValueError,'Incomplete'):validate(verification,{'xp':report},{'xp':{'sha256':'same'}})

 def test_new_profiles_require_complete_text_report(self):
  # Both map reports pass before the additional text gate is checked.
  from unittest.mock import patch
  artifacts={e:{'sha256':e} for e in ('xp','vxa')}
  verification={'passed':True,'artifacts':artifacts}
  row=dict(build='candidate',render_rate=120,logic_fps=120,present_fps=120,missing_fraction=0)
  reports={e:dict(passed=True,profile=profile,hashes={e:{'candidate':e}},results=[row]*10+[dict(row,build='baseline')]*6,regressions=[dict(passed=True,ratios={'mean':1,'p95':1})]*2) for e,profile in [('xp','xp-tile-submit'),('vxa','vxa-map-regression')]}
  with patch('package_tile_client.tile_compare',return_value=[{'passed':True}]):
   with self.assertRaisesRegex(ValueError,'text performance'):validate(verification,reports,artifacts,{'passed':True,'profile':'text-composite','results':[]})
