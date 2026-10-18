"""Finite original/new transition counter semantics; elapsed wall time is diagnostic only."""
import argparse,json,subprocess,sys
from pathlib import Path
from test_runtime import ROOT,run,sha,ORIGINAL_EXE,ORIGINAL_DLL
from test_runtime_graphics import records

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ('exe','original','dll','output'):ap.add_argument(name,type=Path)
 a=ap.parse_args();exe,old,new=[p.resolve() for p in (a.exe,a.original,a.dll)]
 assert sha(exe)==ORIGINAL_EXE and sha(old)==ORIGINAL_DLL
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);probe=ROOT/'tests/rgss_frame_transition_reference.rb'
 with (out/'original.log').open('w') as log:subprocess.run([sys.executable,str(ROOT/'scripts/probe_original_types.py'),str(exe),str(old),str(out/'original'),'--probe',str(probe)],check=True,stdout=log,stderr=subprocess.STDOUT)
 result=run(exe,new,out/'replacement','',probe.read_bytes()+b"\nFile.write('runtime-complete.txt','transition,false,false');sleep 0.3\n",timeout=90)
 left=records(out/'original/types-reference.txt');right=records(out/'replacement/types-reference.txt')
 assert set(left)==set(right)=={kind+str(n) for kind in ('count_','elapsed_') for n in (0,1,2,3,10,20)}|{'count_reset','count_default'}
 different=sorted(key for key in left if key.startswith('count_') and left[key]!=right[key])
 report={'passed':not different,'dll_sha256':result['runtime_sha256'],'original_sha256':ORIGINAL_DLL,'original_records':left,'replacement_records':right,'counter_differences':different,'probe_sha256':sha(probe),'scope':'Frame count before freeze, after freeze and after six finite transition durations. GetTickCount wall intervals retained as diagnostics, not timing equivalence or GPU cost.'}
 (out/'summary.json').write_text(json.dumps(report,indent=2));assert report['passed'],report
 print('Original/replacement transition frame counters: PASS')

if __name__=='__main__':main()
