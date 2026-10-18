import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from migrate_project import transform
from rxdata import read,write

class HighRefreshTests(unittest.TestCase):
 def test_profile_changes_reviewed_timing_and_preserves_entries(self):
  original=read((Path(__file__).resolve().parents[1]/'template/Data/Scripts.rxdata').read_bytes())
  patches,manifest=transform(original,widescreen=True,high_refresh=True)
  result=read(write(original,patches))
  self.assertEqual([(e.id,e.name) for e in original],[(e.id,e.name) for e in result])
  sources={e.name.decode():e.source().decode() for e in result}
  self.assertIn('@duration = duration * 3',sources['Game_Picture'])
  self.assertIn('step_distance',sources['Game_Character 2'])
  self.assertIn('file.timing_rate',sources['Window_SaveFile'])
  self.assertIn('Timing.import_save(file)',sources['Scene_Load'])
  self.assertIn('화면 설정',sources['Scene_Menu'])
  self.assertTrue(any(c.get('reason')=='stock120-timing' for s in manifest for c in s['changes']))

 def test_legacy_conversion_does_not_install_timing_profile(self):
  original=read((Path(__file__).resolve().parents[1]/'template/Data/Scripts.rxdata').read_bytes())
  patches,_=transform(original)
  self.assertNotIn('step_distance',patches.get(0,b'').decode())
  self.assertTrue(all(b'RGSSXP::Timing.import_save' not in source for source in patches.values()))
