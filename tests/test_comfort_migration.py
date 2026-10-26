import hashlib,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from rxdata import read
from migrate_project import transform
from migrate_vxa import transform as vxa_transform

class ComfortMigrationTests(unittest.TestCase):
 def test_stock_installer_is_added_once_without_touching_originals(self):
  for engine,ext,convert in [('xp','rxdata',transform),('vxa','rvdata2',vxa_transform)]:
   with self.subTest(engine=engine):
    path=ROOT/f'template-{engine}/Data/Scripts.{ext}';original=path.read_bytes()
    entries=read(original);main=next(i for i,e in enumerate(entries) if e.name==b'Main')
    for high in (False,True):
     patches,manifest=convert(entries,widescreen=high,high_refresh=high)
     self.assertEqual(patches[main].count(b'Lunetile.install_stock\n'),1)
     expected=entries[main].source()
     if engine=='xp' and high:expected=expected.replace(b'\r\r\n',b'\n').replace(b'\r\n',b'\n')
     self.assertTrue(patches[main].endswith(expected))
     self.assertEqual([row['id'] for row in manifest],[e.id for e in entries])
    self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),hashlib.sha256(original).digest())
