import sys,tempfile,unittest
import shutil
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_discord_review import install_review,prepare,MANUAL_CHECKS,ROOT
from rxdata import read

class DiscordReviewTests(unittest.TestCase):
 def test_default_template_main_line_endings_are_supported(self):
  from benchmark_stock_scripts import source
  for engine,ext in [('xp','rxdata'),('vxa','rvdata2')]:
   with tempfile.TemporaryDirectory(dir=ROOT/'build') as temporary:
    project=Path(temporary);(project/'Data').mkdir()
    shutil.copy2(ROOT/f'template-{engine}/Data/Scripts.{ext}',project/f'Data/Scripts.{ext}')
    self.assertIn(b'$stock_base=',source(project,engine))
 def test_preparation_cannot_claim_overlay_pass_or_overwrite_inputs(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'build') as temporary:
   with self.assertRaisesRegex(ValueError,'already exists'):prepare(ROOT/'build/runtime-native/bin/Release',Path(temporary))
  for name in ['template-xp','template-vxa']:
   with self.assertRaisesRegex(ValueError,'Separate output'):prepare(Path('build/runtime-native/bin/Release'),Path(name)/'review')
 def test_review_uses_stock_source_and_leaves_original_script_bytes(self):
  for engine in ['xp','vxa']:
   for wide in [False,True]:
    with tempfile.TemporaryDirectory(dir=ROOT/'build') as temporary:
     project=Path(temporary);name='Lunetile.dll' if engine=='xp' else 'LunetileVXA.dll'
     (project/name).write_bytes(b'unchanged DLL');(project/'Game.exe').write_bytes(b'launcher')
     encoding='utf-16' if engine=='xp' else 'utf-8'
     (project/'Game.ini').write_text('[Game]\nScripts=Data/original\nTitle=original\n',encoding=encoding)
     with patch('benchmark_stock_scripts.source',return_value=b'# stock prefix\n'),patch('benchmark_stock_scripts.render_probe',return_value=('# scene setup\n','')):
      row=install_review(project,engine,wide)
     self.assertEqual(set(row['checks']),set(MANUAL_CHECKS))
     self.assertTrue(all(r['status']=='not_verified' for r in row['checks'].values()))
     self.assertEqual((project/name).read_bytes(),b'unchanged DLL')
     ext='rxdata' if engine=='xp' else 'rvdata2';body=read((project/f'Review.{ext}').read_bytes())[0].source()
     self.assertIn(b'# stock prefix',body);self.assertIn(b'# scene setup',body)
     self.assertIn(b'discord_overlay_verified:false',body)
     from migrate_project import read_project_ini
     self.assertEqual(read_project_ini(project/'Game.ini')[0].get('Game','Scripts'),'Review.'+ext)
