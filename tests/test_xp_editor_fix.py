import os,re,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from rxdata import read
from migrate_project import transform
ENTRY=ROOT/'src/runtime/xp_entry.rb'
COMPAT=ROOT/'src/runtime/script_compat.rb'
RUBY=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'

# Original RGSS104E stubs; the entry itself must run unchanged under Ruby 1.8.
STUB=r"""
entry = File.read(ARGV.fetch(0))
def text(value); value.dup.force_encoding('UTF-16LE').encode('UTF-8'); end
def wide(value); (value + "\0").encode('UTF-16LE').b; end
$calls = []
# Korean folder name, escaped so the -e source encoding does not matter.
GAME_DIR = "C:\\\uAC8C\uC784\\"
module FileTest
  def self.exist?(path); raise 'wrong DLL' unless path == 'Lunetile.dll'; ENV['CASE'] != 'missing'; end
end
class Win32API
  def initialize(dll, name, *types); @name = name; end
  def call(*args)
    $calls << @name
    case @name
    when 'GetModuleFileNameW'
      path = wide(GAME_DIR + 'Game.EXE')[0..-3]
      args[1][0, path.bytesize] = path
      path.bytesize / 2
    when 'WritePrivateProfileStringW'
      raise 'wrong write' unless args[0..2].map { |value| text(value) } == ["Game\0", "Library\0", "Lunetile.dll\0"]
      raise 'wrong INI' unless text(args[3]) == GAME_DIR + "Game.ini\0"
      ENV['CASE'] == 'write-fail' ? 0 : 1
    when 'GetPrivateProfileStringW'
      raise 'wrong INI' unless text(args[5]) == GAME_DIR + "Game.ini\0"
      value = wide(ENV['CASE'] == 'mismatch' ? 'RGSS104E.dll' : 'Lunetile.dll')[0..-3]
      args[3][0, value.bytesize] = value
      value.bytesize / 2
    when 'ShellExecuteW'
      raise 'wrong exe' unless text(args[2]) == GAME_DIR + "Game.EXE\0"
      expected = {'debug' => 'debug', 'battle' => 'btest'}.fetch(ENV['CASE'], '')
      raise 'wrong flags' unless text(args[3]) == expected + "\0"
      ENV['CASE'] == 'launch-fail' ? 31 : 42
    end
  end
end
module RGSSXP; end if ENV['CASE'] == 'lunetile'
$DEBUG = %w[debug battle].include?(ENV['CASE'])
$BTEST = ENV['CASE'] == 'battle'
begin
  eval(entry)
  raise 'entry returned' unless ENV['CASE'] == 'lunetile' && $calls.empty?
rescue SystemExit
  raise 'exit without launch' unless %w[normal debug battle].include?(ENV['CASE']) && $calls.last == 'ShellExecuteW'
rescue RuntimeError => error
  expected = {'missing' => 'missing', 'write-fail' => 'Cannot restore', 'mismatch' => 'Cannot restore', 'launch-fail' => 'Cannot restart'}[ENV['CASE']]
  raise unless expected && error.message.include?(expected)
end
"""

class XPEditorFixTests(unittest.TestCase):
 @unittest.skipUnless(RUBY.is_file(),'built rgssxp-ruby.exe required')
 def test_entry_restores_library_and_relaunches_with_test_flags(self):
  for case in ('normal','debug','battle','lunetile','missing','write-fail','mismatch','launch-fail'):
   result=subprocess.run([str(RUBY),'--disable-gems','-e',STUB,str(ENTRY)],env={**os.environ,'CASE':case},capture_output=True,text=True,encoding='utf-8')
   self.assertEqual(result.returncode,0,(case,result.stderr))
 def test_entry_avoids_ruby_19_syntax(self):
  code=[line for line in ENTRY.read_text(encoding='utf-8').splitlines() if not line.lstrip().startswith('#')]
  self.assertTrue(ENTRY.read_bytes().isascii())
  for pattern in (r'->',r'&\.',r'\.encode\b',r'force_encoding',r'\.b\b',r'\b\w+: ',r'\.then\b',r'__dir__'):
   self.assertFalse(any(re.search(pattern,line) for line in code),pattern)
 def test_migration_prepends_entry_to_first_script(self):
  entries=read((ROOT/'template-xp/Data/Scripts.rxdata').read_bytes())
  patches,manifest=transform(entries)
  self.assertEqual(entries[0].name,b'Game_Temp')
  self.assertTrue(patches[0].startswith(ENTRY.read_bytes()))
  self.assertTrue(patches[0].endswith(entries[0].source().replace(b'\r\n',b'\n')))
  self.assertIn('restore Lunetile.dll after RPG Maker XP editor save',[change.get('reason') for change in manifest[0]['changes']])
 @unittest.skipUnless(RUBY.is_file(),'built rgssxp-ruby.exe required')
 def test_manual_editor_fix_entry_is_not_audited_as_custom(self):
  result=subprocess.run([str(RUBY),'--disable-gems','-e','load ARGV[0]; s = File.read(ARGV[1]); raise unless RGSSXP::ScriptAudit.editor_fix?(s) && !RGSSXP::ScriptAudit.editor_fix?("p 1\\n" + s)',str(COMPAT),str(ENTRY)],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
 def test_editor_fix_archive_contains_only_entry_and_instructions(self):
  from package_template import editor_fix_archive
  (ROOT/'build').mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(dir=ROOT/'build') as tmp:
   target=Path(tmp)/'fix.zip';editor_fix_archive(target)
   with zipfile.ZipFile(target) as zipped:
    self.assertEqual(set(zipped.namelist()),{'LunetileEditorFix.rb','README.txt'})
    self.assertEqual(zipped.read('LunetileEditorFix.rb'),ENTRY.read_bytes())

if __name__=='__main__':unittest.main()
