"""Compare full GDI text pixels and extents against preserved XP/VXA DLLs."""
import argparse,json
from pathlib import Path
from benchmark_runtime_client import ROOT,launch
from test_runtime import sha

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('output',type=Path);ap.add_argument('--baseline',type=Path,required=True)
 args=ap.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
 rows=[]
 for engine,name in [('xp','Lunetile.dll'),('vxa','LunetileVXA.dll')]:
  folders=[];hashes={}
  for label,dll in [('baseline',args.baseline.resolve()/name),('candidate',ROOT/'build/runtime-native/bin/Release'/name)]:
   folder=out/engine/label;launch(engine,dll,folder,(ROOT/'tests/runtime_text_pixels.rb').read_bytes())
   folders.append(folder);hashes[label]=sha(dll)
  old,new=folders
  assert (old/'text-pixels.bin').read_bytes()==(new/'text-pixels.bin').read_bytes(),engine+' text pixel mismatch'
  metrics=json.loads((new/'text-pixels.json').read_text(encoding='utf-8'))
  assert json.loads((old/'text-pixels.json').read_text(encoding='utf-8'))==metrics,engine+' text extent mismatch'
  rows.append(dict(engine=engine,dll_sha256=hashes,cases=len(metrics),pixel_sha256=sha(new/'text-pixels.bin'),bytes=(new/'text-pixels.bin').stat().st_size))
 (out/'summary.json').write_text(json.dumps(dict(passed=True,results=rows),indent=2)+'\n',encoding='utf-8')
 print('XP/VXA full text pixels and extents PASS')

if __name__=='__main__':main()
