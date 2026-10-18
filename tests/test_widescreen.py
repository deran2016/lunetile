import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from migrate_project import transform,MigrationError
from rxdata import read,write

class WidescreenTests(unittest.TestCase):
 def setUp(self):
  self.raw=(Path(__file__).resolve().parents[1]/'template/Data/Scripts.rxdata').read_bytes()
  self.entries=read(self.raw)

 def test_stock_layout_is_opt_in_and_preserves_script_identity(self):
  legacy,_=transform(self.entries)
  wide,mapping=transform(self.entries,True)
  converted=read(write(self.entries,wide))
  self.assertEqual([(e.id,e.name) for e in converted],[(e.id,e.name) for e in self.entries])
  sources={e.name.decode():e.source().decode() for e in converted}
  self.assertIn('Lunetile.map_rect',sources['Spriteset_Map'])
  self.assertIn('Graphics.height - 160',sources['Window_BattleStatus'])
  self.assertIn('module Lunetile',sources['Main'])
  self.assertGreater(len(wide),len(legacy))
  self.assertNotIn('Lunetile.map_rect',self.entries[next(i for i,e in enumerate(self.entries) if e.name==b'Spriteset_Map')].source().decode())
  self.assertTrue(any(c.get('reason')=='widescreen-layout' for m in mapping for c in m['changes']))

 def test_unreviewed_source_is_rejected_before_wide_patches(self):
  import zlib
  self.entries[0].compressed=zlib.compress(self.entries[0].source()+b'\nputs :custom')
  with self.assertRaises(MigrationError):transform(self.entries,True)
