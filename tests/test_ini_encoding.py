"""The unchanged launcher's A API and runtime's W API must agree on migrated INI values."""
import configparser,ctypes,os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from migrate_project import read_project_ini,MigrationError
TEMP_ROOT=Path(__file__).resolve().parents[1]/'build'

class IniEncodingTests(unittest.TestCase):
 def test_explicit_source_encodings_and_boms(self):
  TEMP_ROOT.mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as folder:
   assert Path(folder).resolve().is_relative_to(TEMP_ROOT.resolve())
   path=Path(folder)/'Game.ini'
   for encoding,title in [('CP949','한글 테스트'),('CP932','日本語テスト'),('UTF-8','한글 UTF8')]:
    path.write_bytes(('[Game]\nTitle='+title+'\n').encode(encoding))
    with self.assertRaises(MigrationError):read_project_ini(path)
    ini,actual=read_project_ini(path,encoding)
    self.assertEqual((ini.get('Game','Title'),actual),(title,encoding))
   for encoding in ('utf-16','utf-8-sig'):
    path.write_text('[Game]\nTitle=한글\n',encoding=encoding)
    self.assertEqual(read_project_ini(path)[0].get('Game','Title'),'한글')
   path.write_bytes(b'[Game]\nTitle=\xff\n')
   with self.assertRaises(MigrationError):read_project_ini(path,'UTF-8')

 @unittest.skipUnless(os.name=='nt','Windows profile API check')
 def test_windows_ansi_and_unicode_profile_reads(self):
  kernel=ctypes.WinDLL('kernel32',use_last_error=True)
  wide=kernel.GetPrivateProfileStringW;wide.argtypes=[ctypes.c_wchar_p]*4+[ctypes.c_uint,ctypes.c_wchar_p];wide.restype=ctypes.c_uint
  ansi=kernel.GetPrivateProfileStringA;ansi.argtypes=[ctypes.c_char_p]*4+[ctypes.c_uint,ctypes.c_char_p];ansi.restype=ctypes.c_uint
  with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as folder:
   assert Path(folder).resolve().is_relative_to(TEMP_ROOT.resolve())
   path=Path(folder)/'Game.ini'
   ini=configparser.ConfigParser(interpolation=None)
   ini['Game']={'Title':'한글 프로젝트','Library':'Lunetile.dll','Scripts':'Data/Scripts.rxdata'}
   with path.open('w',encoding='utf-16') as stream:ini.write(stream,space_around_delimiters=False)
   self.assertTrue(path.read_bytes().startswith(b'\xff\xfe'))
   for name,value in ini['Game'].items():
    buffer=ctypes.create_unicode_buffer(512)
    self.assertEqual(wide('Game',name,'',buffer,512,str(path)),len(value))
    self.assertEqual(buffer.value,value)
    try:expected=value.encode('mbcs',errors='strict')
    except UnicodeEncodeError:continue
    raw=ctypes.create_string_buffer(512)
    self.assertEqual(ansi(b'Game',name.encode(),b'',raw,512,str(path).encode('mbcs')),len(expected))
    self.assertEqual(raw.value,expected)

if __name__=='__main__':unittest.main()
