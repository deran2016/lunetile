"""Compare an explicit Reset exception with original RGSS; physical F12 is separate."""
import argparse,json,subprocess,sys
from pathlib import Path
from test_runtime import ROOT,run
from test_runtime_graphics import records

def main():
 ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('original_dll',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('output',type=Path)
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 command=[sys.executable,str(ROOT/'scripts/probe_original_types.py'),str(a.exe.resolve()),str(a.original_dll.resolve()),str(out/'original'),'--probe',str(ROOT/'tests/rgss_reset_reference.rb')]
 with (out/'original.log').open('w') as log:subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
 result=run(a.exe.resolve(),a.dll.resolve(),out/'replacement','',(ROOT/'tests/rgss_reset_reference.rb').read_bytes(),timeout=120)
 before=records(out/'original/types-reference.txt');after=records(out/'replacement/types-reference.txt')
 # XP's Viewport has no public disposed?; the new display registry has an extra diagnostic getter.
 assert before['entry2'][5][1]=='NoMethodError' and after['entry2'][5][1] is True
 before['entry2'][5].pop(1);after['entry2'][5].pop(1)
 assert before==after,{'original':before,'replacement':after}
 assert result['log'].count('Ruby Reset:')==1 and result['log'].count('Ruby initialized:')==1
 (out/'summary.json').write_text(json.dumps({'passed':True,'scope':'Explicit Reset exception; globals/Font/frame_count retained, 40Hz restored, native objects disposed, scripts rerun without VM restart','records':before,'runtime':result},indent=2))
 print('Reset state/resource lifetime and script reload: PASS')

if __name__=='__main__':main()
