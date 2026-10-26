import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'example/tools')]
from rxdata import read,write
from migrate_project import transform
from prepare_example import reviewed_performance

class MMOPerformanceTests(unittest.TestCase):
 def converted(self):
  entries=read((ROOT/'template-xp/Data/Scripts.rxdata').read_bytes())
  changes,_=transform(entries,widescreen=True,high_refresh=True)
  return read(write(entries,changes))
 def test_latest_and_legacy_reviewed_sources_get_the_same_optimization(self):
  entries=self.converted();helper,latest=reviewed_performance(entries)
  self.assertIn(b'Lunetile::StockScripts.install(::Sprite_Character,:update',helper)
  self.assertIn(b'lunetile_move_remainder',helper)
  self.assertNotIn(b'Lunetile.install_stock',helper)
  main=next(i for i,e in enumerate(entries) if e.name==b'Main')
  legacy=read(write(entries,{main:latest.removeprefix(b'Lunetile.install_stock\n')}))
  self.assertEqual(reviewed_performance(legacy)[0],helper)
  tail=next(e.source().replace(b'\r\n',b'\n') for e in read((ROOT/'template-xp/Data/Scripts.rxdata').read_bytes()) if e.name==b'Main')
  for source in (latest,latest.removeprefix(b'Lunetile.install_stock\n')):
   optimized=read(write(entries,{main:source[:-len(tail)]+helper+b'\n'+tail}))
   self.assertEqual(reviewed_performance(optimized)[0],helper)
 def test_custom_methods_and_startup_are_never_overwritten_by_optimization(self):
  entries=self.converted()
  for index in [0,next(i for i,e in enumerate(entries) if e.name==b'Main')]:
   changed=read(write(entries,{index:b'# custom\n'+entries[index].source()}))
   self.assertIsNone(reviewed_performance(changed)[0])
 def test_partial_or_reordered_collections_are_not_optimized(self):
  entries=self.converted();self.assertIsNone(reviewed_performance(entries[:-1])[0])
  entries[0],entries[1]=entries[1],entries[0]
  self.assertIsNone(reviewed_performance(entries)[0])
