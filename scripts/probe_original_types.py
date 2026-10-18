"""Collect primitive RGSS type behavior without copying proprietary source."""
import argparse,ast,json,shutil,subprocess
from pathlib import Path
from test_runtime import ROOT,sha,scripts,ORIGINAL_EXE,ORIGINAL_DLL

def main():
 ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('output',type=Path)
 ap.add_argument('--probe',type=Path,default=ROOT/'tests/rgss_types_reference.rb')
 ap.add_argument('--data',type=Path)
 a=ap.parse_args();out=a.output.resolve()
 assert sha(a.exe)==ORIGINAL_EXE and sha(a.dll)==ORIGINAL_DLL
 out.mkdir(parents=True,exist_ok=False)
 shutil.copy2(a.exe,out/'Game.exe');shutil.copy2(a.dll,out/'RGSS104E.dll')
 if a.data:shutil.copytree(a.data,out/'Data',ignore=shutil.ignore_patterns('Scripts.rxdata'))
 (out/'Scripts.rxdata').write_bytes(scripts(a.probe.read_bytes()))
 (out/'Game.ini').write_text('[Game]\nLibrary=RGSS104E.dll\nScripts=Scripts.rxdata\nTitle=RGSS Type Reference\nRTP1=\nRTP2=\nRTP3=\n')
 p=subprocess.Popen([str(out/'Game.exe')],cwd=out)
 try:p.wait(timeout=20)
 finally:
  if p.poll() is None:p.terminate();p.wait()
 assert p.returncode==0
 records={}
 for line in (out/'types-reference.txt').read_text().splitlines():
  name,value=line.split('\t',1)
  records[name]=ast.literal_eval(value.replace('nil','None').replace('false','False').replace('true','True'))
 (out/'results.json').write_text(json.dumps(records,indent=2))
 print(json.dumps(records,indent=2))

if __name__=='__main__':main()
