import ast,json,re,subprocess,sys,tempfile,unittest,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from rxdata import Entry,read
from migrate_project import CHECKER,MigrationError,RUNTIME_BIN,transform

EIGHT_DIRECTION=b'class Game_Player < Game_Character\ndef passable? (x, y, d)\nnew_x = x\nunless $game_map.valid? (new_x, y)\nreturn false\nend\nif $DEBUG and Input.press? (Input::CTRL)\nreturn true\nend\nsuper\nend\nend\n'
COMPAT=ROOT/'src/runtime/script_compat.rb'
RUBY=RUNTIME_BIN/'rgssxp-ruby.exe'

def entry(name,source,id=1):
 return Entry(id,name,zlib.compress(source),b'')

def adapted_methods(module):
 """Stock methods whose bodies a profile adapter rewrites, after the base migration RULES."""
 from migrate_project import RULES
 result={}
 for item in read((ROOT/'template-xp/Data/Scripts.rxdata').read_bytes()):
  name=item.name.decode('utf-8')
  if name=='Main':continue
  text=item.source().decode('utf-8').replace('\r\n','\n')
  for before,after in RULES.get(name,[]):text=text.replace(before,after)
  _,changes=module.adapt(name,text);lines=text.split('\n')
  for change in changes:
   index=change['line']-1
   while not re.match(r'\s*def ',lines[index]):index-=1
   result.setdefault(re.sub(r' \d+$','',name),set()).add(re.match(r'\s*def\s+(\w+[?!=]?)',lines[index]).group(1))
 return result

class CustomScriptMigrationTests(unittest.TestCase):
 def setUp(self):
  self.stock=read((ROOT/'template-xp/Data/Scripts.rxdata').read_bytes())
  self.custom=[entry(b'',b''),entry('Advanced Message Script'.encode(),b'class AMS; end\n',2),entry(b'8_direction_movement',EIGHT_DIRECTION,3)]
  self.entries=self.stock[:-1]+self.custom+self.stock[-1:]
 def test_custom_block_above_main_is_kept_verbatim(self):
  patches,manifest=transform(self.entries,custom_scripts=True)
  first=len(self.stock)-1
  for offset,item in enumerate(self.custom):
   row=manifest[first+offset]
   self.assertEqual(row['kind'],'custom')
   self.assertEqual(row['changes'],[])
   self.assertNotIn(first+offset,patches)
  self.assertEqual([row['name'] for row in manifest][-1],'Main')
  self.assertIn(len(self.entries)-1,patches)
 def test_default_still_rejects_custom_scripts(self):
  with self.assertRaisesRegex(MigrationError,'--custom-scripts'):transform(self.entries)
 def test_custom_scripts_reject_layout_and_profile_conflicts(self):
  with self.assertRaisesRegex(MigrationError,'stay above Main'):transform(self.stock+self.custom,custom_scripts=True)
  with self.assertRaisesRegex(MigrationError,'identity/order'):transform(self.custom+self.stock,custom_scripts=True)
  edited=list(self.entries);edited[0]=entry(self.stock[0].name,self.stock[0].source()+b'\n# edit\n')
  with self.assertRaisesRegex(MigrationError,'unreviewed source'):transform(edited,custom_scripts=True)
  for options in ({'widescreen':True},{'high_refresh':True}):
   with self.assertRaisesRegex(MigrationError,'cannot be combined'):transform(self.entries,custom_scripts=True,**options)
 def test_audit_tables_match_stock_names_and_adapted_methods(self):
  text=COMPAT.read_text(encoding='utf-8')
  stock=ast.literal_eval('['+re.search(r'STOCK_NAMES = \[(.*?)\]\.freeze',text,re.S).group(1)+']')
  self.assertEqual(stock,[row['name'] for row in json.loads((ROOT/'src/runtime/stock_scripts.json').read_text())['scripts']])
  import widescreen,high_refresh
  for profile,module in (('widescreen',widescreen),('stock120',high_refresh)):
   block=re.search(profile+r': \{(.*?)\}\.freeze',text,re.S).group(1)
   table={name:set(methods.split()) for name,methods in re.findall(r"'(\w+)' => %w\[(.*?)\]",block)}
   self.assertEqual(table,adapted_methods(module),profile)

@unittest.skipUnless(RUBY.is_file(),'built rgssxp-ruby.exe required')
class LegacySyntaxRepairTests(unittest.TestCase):
 def ruby(self,code,*args):
  return subprocess.run([str(RUBY),'--disable-gems','-e',code,str(COMPAT),*map(str,args)],capture_output=True,text=True,encoding='utf-8')
 def repair(self,source):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'source.rb';path.write_bytes(source)
   result=self.ruby('load ARGV.shift; r = RGSSXP::LegacySyntax.repair(File.binread(ARGV[0]).force_encoding("UTF-8"), "t"); print r ? r[0] : "NIL"',path)
  self.assertEqual(result.returncode,0,result.stderr)
  return result.stdout
 def test_eight_direction_lines_are_repaired_only_where_parser_fails(self):
  fixed=self.repair(EIGHT_DIRECTION)
  self.assertIn('$game_map.valid?(new_x, y)',fixed)
  self.assertIn('def passable? (x, y, d)',fixed)
  self.assertIn('Input.press? (Input::CTRL)',fixed)
 def test_strings_comments_and_keywords_are_untouched(self):
  fixed=self.repair(b'x = foo (1, 2)  # bar (3, 4)\nputs "baz (5, 6)"\n')
  self.assertEqual(fixed,'x = foo(1, 2)  # bar (3, 4)\nputs "baz (5, 6)"\n')
  self.assertEqual(self.repair(b'p 1\n'),'NIL')
  self.assertEqual(self.repair(b'def broken(\n'),'NIL')
 def test_migration_checker_reports_runtime_repairs(self):
  with tempfile.TemporaryDirectory() as directory:
   good=Path(directory)/'000.rb';good.write_bytes(b'p 1\n')
   legacy=Path(directory)/'001.rb';legacy.write_bytes(EIGHT_DIRECTION)
   result=subprocess.run([str(RUBY),'--disable-gems','-e',CHECKER,str(COMPAT),str(good),str(legacy)],capture_output=True,text=True,encoding='utf-8')
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertIn('001.rb: runtime repairs Ruby 1.8 call syntax on lines 4',result.stdout)
   self.assertTrue(result.stdout.endswith('2 scripts compile\n'))
   legacy.write_bytes(b'def broken(\n')
   self.assertNotEqual(subprocess.run([str(RUBY),'--disable-gems','-e',CHECKER,str(COMPAT),str(legacy)],capture_output=True).returncode,0)

if __name__=='__main__':unittest.main()
