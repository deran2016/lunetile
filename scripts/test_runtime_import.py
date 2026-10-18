"""Original game-save object graph comparison, followed by new-format save/reload."""
import argparse,json,shutil,subprocess
from pathlib import Path
from rxdata import read
from test_runtime import ROOT,run,scripts,sha,ORIGINAL_EXE,ORIGINAL_DLL
from test_runtime_data import read_graphs

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('project',type=Path);ap.add_argument('original_dll',type=Path);ap.add_argument('replacement_dll',type=Path)
 ap.add_argument('save',type=Path);ap.add_argument('output',type=Path)
 a=ap.parse_args();exe=(a.project/'Game.exe').resolve();data=(a.project/'Data').resolve();out=a.output.resolve()
 assert sha(exe)==ORIGINAL_EXE and sha(a.original_dll)==ORIGINAL_DLL
 original_hash=sha(a.save)
 entries=read((data/'Scripts.rxdata').read_bytes())
 # Game-state classes contain no rendering superclass and can be tested independently.
 game_source=b'\n'.join(entry.source() for entry in entries if entry.name.startswith((b'Game_',b'Interpreter ')))
 source=game_source+b'\n'+(ROOT/'tests/runtime_data.rb').read_bytes()+(ROOT/'tests/runtime_import.rb').read_bytes()
 baseline=out/'original';baseline.mkdir(parents=True,exist_ok=False)
 shutil.copy2(exe,baseline/'Game.exe');shutil.copy2(a.original_dll,baseline/'RGSS104E.dll')
 shutil.copytree(data,baseline/'Data',ignore=shutil.ignore_patterns('Scripts.rxdata'))
 (baseline/'Saves/Import').mkdir(parents=True);shutil.copy2(a.save,baseline/'Saves/Import/Save1.rxdata')
 (baseline/'Scripts.rxdata').write_bytes(scripts(source))
 (baseline/'Game.ini').write_text('[Game]\nLibrary=RGSS104E.dll\nScripts=Scripts.rxdata\nTitle=Original save graph\nRTP1=\nRTP2=\nRTP3=\n')
 p=subprocess.Popen([str(baseline/'Game.exe')],cwd=baseline)
 try:p.wait(timeout=20)
 finally:
  if p.poll() is None:p.terminate();p.wait()
 assert p.returncode==0 and (baseline/'runtime-complete.txt').read_text()=='import,false,false'
 result=run(exe,a.replacement_dll.resolve(),out/'replacement','',source,data=data,import_save=a.save)
 expected=read_graphs(baseline/'types-reference.txt');actual=read_graphs(out/'replacement/types-reference.txt')
 assert expected==actual,{'mismatch':[name for name in expected if expected[name]!=actual.get(name)]}
 assert sha(a.save)==original_hash and sha(out/'replacement/Saves/Import/Save1.rxdata')==original_hash
 report={'passed':True,'original_save_sha256':original_hash,'project_data_files':len(actual)-1,'save_graph_records':len(actual['original-save']),'runtime':result}
 (out/'comparison.json').write_text(json.dumps(report,indent=2))
 print('Original RGSS save import, full graph equality, engine-format save/reload, original preservation: PASS')

if __name__=='__main__':main()
