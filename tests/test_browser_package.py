import hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from package_browser import demo_scripts,package
from rxdata import read

class BrowserPackageTests(unittest.TestCase):
 def test_demo_script_name_and_unicode_source_round_trip(self):
  source='# 브라우저 예제\nputs "hello"\n'.encode()
  entries=read(demo_scripts(source))
  self.assertEqual(len(entries),1);self.assertEqual(entries[0].name,b'Lunetile browser demo');self.assertEqual(entries[0].source(),source)
 def test_unpassed_verification_does_not_create_output(self):
  root=Path(__file__).resolve().parents[1]/'build';root.mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(dir=root) as temporary:
   p=Path(temporary);runtime=p/'runtime';runtime.mkdir();report=p/'verification.json'
   for data in ({'passed':False},{'passed':True,'performance':{'passed':False}}):
    report.write_text(json.dumps(data))
    with self.assertRaisesRegex(ValueError,'Passed runtime'):package(runtime,report,p/'output')
    self.assertFalse((p/'output').exists())
