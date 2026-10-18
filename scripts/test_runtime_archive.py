"""Compare RGSSAD lookup priority, case handling and key progression against RGSS1."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
from test_runtime import ROOT,run,scripts,sha,ORIGINAL_EXE,ORIGINAL_DLL
from rxdata import integer,string
sys.path.insert(0,str(ROOT/'tests'))
from rgssad_fixture import pack

def main():
 ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('original_dll',type=Path)
 ap.add_argument('replacement_dll',type=Path);ap.add_argument('output',type=Path)
 a=ap.parse_args();out=a.output.resolve();exe=a.exe.resolve()
 assert sha(exe)==ORIGINAL_EXE and sha(a.original_dll)==ORIGINAL_DLL
 source=(ROOT/'tests/runtime_archive.rb').read_bytes()
 archived=b'\x04\x08['+integer(2)+b'i'+integer(42)+string(b'archive')
 entries=[(b'Data\\Scripts.rxdata',scripts(source)),(b'Data\\probe.rxdata',archived)]
 for length in range(1,8):entries.append((f'Data\\bytes{length}.rxdata'.encode(),b'\x04\x08'+string(b'x'*length)))
 blob=pack(entries)
 baseline=out/'original';baseline.mkdir(parents=True,exist_ok=False)
 shutil.copy2(exe,baseline/'Game.exe');shutil.copy2(a.original_dll,baseline/'RGSS104E.dll')
 (baseline/'Game.rgssad').write_bytes(blob)
 (baseline/'Game.ini').write_text('[Game]\nLibrary=RGSS104E.dll\nScripts=Data\\Scripts.rxdata\nTitle=Original archive test\nRTP1=\nRTP2=\nRTP3=\n')
 # Conflicting disk file determines original archive-vs-disk priority.
 fixture=out/'loose-data';fixture.mkdir()
 (fixture/'probe.rxdata').write_bytes(b'\x04\x08['+integer(2)+b'i'+integer(99)+string(b'disk'))
 shutil.copytree(fixture,baseline/'Data')
 p=subprocess.Popen([str(baseline/'Game.exe')],cwd=baseline)
 try:p.wait(timeout=20)
 finally:
  if p.poll() is None:p.terminate();p.wait()
 assert p.returncode==0 and (baseline/'runtime-complete.txt').exists()
 results=[]
 for name in ('replacement','한글 경로'):
  result=run(exe,a.replacement_dll.resolve(),out/name,'',source,data=fixture,archive=blob)
  assert (out/name/'types-reference.txt').read_bytes()==(baseline/'types-reference.txt').read_bytes()
  results.append(result)
 (out/'comparison.json').write_text(json.dumps({'passed':True,'entry_count':len(entries),'lookup_reference':(baseline/'types-reference.txt').read_text(),'runs':results},ensure_ascii=False,indent=2),encoding='utf-8')
 print('Original/new RGSSAD v1: key progression, tail bytes, case, lookup priority, Korean project path PASS')

if __name__=='__main__':main()
