"""Unknown event Ruby is rejected and non-ASCII data requires explicit encoding."""
import argparse,configparser,json,shutil
from pathlib import Path
from test_runtime import ROOT,run,sha
from migrate_project import migrate,MigrationError

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('ruby',type=Path);ap.add_argument('output',type=Path)
 ap.add_argument('--original-dll',type=Path)
 a=ap.parse_args();out=a.output.resolve()
 run((a.project/'Game.exe').resolve(),a.dll.resolve(),out/'fixture-driver','',(ROOT/'tests/runtime_migration_fixtures.rb').read_bytes(),data=a.project/'Data')
 results=[]
 for case,expected in [('event-code','event script line 1'),('condition-code','event script line 1'),('movement-code','movement script line 1'),('utf8-text','--data-encoding UTF-8')]:
  source=out/case;source.mkdir();shutil.copy2(a.project/'Game.exe',source/'Game.exe');shutil.copytree(a.project/'Data',source/'Data')
  shutil.copy2(out/'fixture-driver'/(case+'.rxdata'),source/'Data/Map001.rxdata')
  digest=sha(source/'Data/Map001.rxdata')
  try:migrate(source,out/(case+'-result'),a.dll,a.ruby)
  except MigrationError as error:
   assert expected in str(error) and 'Map001.rxdata' in str(error),str(error)
   assert not (out/(case+'-result')).exists()
   results.append({'case':case,'rejected':True})
  else:raise AssertionError('Unreviewed source or ambiguous data text was accepted: '+case)
  assert sha(source/'Data/Map001.rxdata')==digest
 source=out/'utf8-text'
 (source/'Game.ini').write_text('[game]\nlibrary=old-engine.dll\nscripts=Data\\Scripts.rxdata\nrtp1=\n[rgssxp]\nsaveformat=0\n')
 if a.original_dll:shutil.copy2(a.original_dll,source/'renamed-original.dll')
 manifest=migrate(source,out/'utf8-explicit-result',a.dll,a.ruby,'UTF-8')
 assert manifest['data_encoding_explicit']
 ini=configparser.ConfigParser();ini.read(out/'utf8-explicit-result/Game.ini',encoding='utf-16')
 assert ini.get('Game','Library')=='RGSS104E.dll' and ini.get('RGSSXP','SaveFormat')=='1'
 if a.original_dll:
  assert not (out/'utf8-explicit-result/renamed-original.dll').exists()
  assert any(entry['path']=='renamed-original.dll' for entry in manifest['removed_engine_files'])
 (out/'comparison.json').write_text(json.dumps({'passed':True,'rejections':results,'explicit_utf8_accepted':True},indent=2))
 print('Event/condition/movement Ruby rejection + explicit UTF-8 + failed-migration cleanup: PASS')

if __name__=='__main__':main()
