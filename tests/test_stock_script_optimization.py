import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from rxdata import read,write
from migrate_project import transform as xp_transform
from migrate_vxa import transform as vxa_transform
from optimize_template_scripts import optimize,scalar_moves,positions
from benchmark_stock_scripts import save

class StockScriptOptimizationTests(unittest.TestCase):
 def project(self,engine):
  (ROOT/'build').mkdir(exist_ok=True)
  temp=tempfile.TemporaryDirectory(dir=ROOT/'build');self.addCleanup(temp.cleanup)
  p=Path(temp.name);(p/'Data').mkdir();(p/'migration').mkdir()
  ext='rxdata' if engine=='xp' else 'rvdata2'
  entries=read((ROOT/f'template-{engine}/Data/Scripts.{ext}').read_bytes())
  changes,mapping=(xp_transform if engine=='xp' else vxa_transform)(entries,widescreen=True,high_refresh=True)
  path=p/f'Data/Scripts.{ext}';path.write_bytes(write(entries,changes))
  (p/'migration/manifest.json').write_text(json.dumps({'scripts':mapping}))
  return p,path
 def test_only_main_payload_changes_and_general_transform_stays_identical(self):
  for engine in ('xp','vxa'):
   with self.subTest(engine=engine):
    p,path=self.project(engine);before=path.read_bytes();entries=read(before)
    with patch('optimize_template_scripts.subprocess.run',return_value=subprocess.CompletedProcess([],0,'Syntax OK\n','')):
     report=optimize(p,engine,Path('bootstrap-ruby'))
    after=read(path.read_bytes());main=report['main_index']
    self.assertEqual([(e.id,e.name) for e in entries],[(e.id,e.name) for e in after])
    self.assertEqual(report['unchanged_entries'],len(entries)-1)
    for i,e in enumerate(entries):
     if i!=main:self.assertEqual(e.raw,after[i].raw)
    self.assertIn(b'Lunetile::StockScripts.install',after[main].source())
    original=(ROOT/f'template-{engine}/Data/Scripts.{"rxdata" if engine=="xp" else "rvdata2"}').read_bytes()
    es=read(original);changes,_=(xp_transform if engine=='xp' else vxa_transform)(es,widescreen=True,high_refresh=True)
    self.assertEqual(write(es,changes),before)
    with self.assertRaisesRegex(ValueError,'Unreviewed'):optimize(p,engine,Path('bootstrap-ruby'))
 def test_modified_source_is_rejected_without_rewriting(self):
  for engine in ('xp','vxa'):
   p,path=self.project(engine);path.write_bytes(write(read(path.read_bytes()),{0:b'# modified'}));before=path.read_bytes()
   with self.assertRaisesRegex(ValueError,'Unreviewed'):optimize(p,engine,Path('bootstrap-ruby'))
   self.assertEqual(path.read_bytes(),before)
 def test_syntax_failure_does_not_replace_script_or_manifest(self):
  p,path=self.project('xp');before=path.read_bytes();manifest=(p/'migration/manifest.json').read_bytes()
  with patch('optimize_template_scripts.subprocess.run',return_value=subprocess.CompletedProcess([],1,'','syntax failure')):
   with self.assertRaisesRegex(ValueError,'syntax failed'):optimize(p,'xp',Path('bootstrap-ruby'))
  self.assertEqual(path.read_bytes(),before);self.assertEqual((p/'migration/manifest.json').read_bytes(),manifest)
 def test_scalar_clamp_keeps_first_operand_on_equal_values(self):
  source='  def update_move\n    @real_x = [@real_x + distance, @x].min if @x > @real_x\n  end\n'
  result=scalar_moves(source)
  self.assertIn('lunetile_value > lunetile_bound ? lunetile_bound : lunetile_value',result)
  self.assertIn('if @x > @real_x',result);self.assertNotIn('.min',result)
  self.assertEqual(positions('    @x = value\n'),'    @x = value; Lunetile::StockScripts.moved(self); @x\n')
 def test_save_benchmark_rejects_different_dlls_before_execution(self):
  (ROOT/'build').mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(dir=ROOT/'build') as temporary:
   root=Path(temporary)
   for name in ('baseline','candidate'):
    folder=root/name/'vxa';folder.mkdir(parents=True)
    (folder/'LunetileVXA.dll').write_bytes(name.encode())
   with patch('benchmark_stock_scripts.run') as execute:
    with self.assertRaisesRegex(ValueError,'same DLL'):save(root/'baseline',root/'candidate',root/'out')
    execute.assert_not_called()
