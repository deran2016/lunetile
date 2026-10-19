"""Original-only in-memory wait observation; headline frame comparisons remain unhooked."""
import argparse,csv,json,statistics
from pathlib import Path
from benchmark_runtime import run_case,percentile
from test_runtime import ROOT,ORIGINAL_EXE,ORIGINAL_DLL,sha,run
from rxdata import read

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);ap.add_argument('fixture',type=Path);ap.add_argument('original_dll',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--frames',type=int,default=240)
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 exe=(a.project/'Game.exe').resolve();dll=a.original_dll.resolve();observer=ROOT/'build/runtime-native/bin/Release/RGSSWaitObserver.dll'
 assert sha(exe)==ORIGINAL_EXE and sha(dll)==ORIGINAL_DLL
 before={str(p):sha(p) for p in (exe,dll,a.project/'Data/Scripts.rxdata')}
 # The observer must refuse a replacement runtime before touching any import.
 probe=("observer=Win32API.new("+repr(str(observer).replace('\\','/'))+",'WaitObserveStart','','I'); raise 'Wrong runtime accepted' unless observer.call<0; File.write('runtime-complete.txt','observer-reject,false,false'); sleep 0.5").encode()
 run(exe,ROOT/'build/runtime-native/bin/Release/Lunetile.dll',out/'wrong-runtime','',probe)
 entries=read((a.project/'Data/Scripts.rxdata').read_bytes())
 source=b'\n'.join(e.source() for e in entries[:-1])+b'\n'+(ROOT/'tests/runtime_wait_profile.rb').read_bytes()+b'\nbegin\n'+(ROOT/'tests/runtime_bench.rb').read_bytes()+b'\nensure\n WaitProfile.finish\nend\n'
 case=run_case(a.fixture.resolve(),exe,dll,ROOT/'build/runtime-native/bin/Release/RGSSBenchMetrics.dll',source,out/'original',a.frames,extra_modules=(observer,))
 assert (out/'original/wait-observer-restored.txt').read_text()=='original-import-restored'
 rows=list(csv.DictReader((out/'original/wait-parts.csv').open()));report={'passed':False,'original_sha256':sha(dll),'observer_sha256':sha(observer),'scope':'Separate original-only diagnostic. Exact pinned frame-loop MsgWaitForMultipleObjects import observed in memory, identical arguments/return forwarded; no timer/GC policy change. Includes QPC observer overhead; primary paired frame timings contain no hook. Non-wait wall time is not CPU execution time. Import restored and re-attach validated.','stages':[],'benchmark':case}
 for stage in range(4):
  selected=[r for r in rows if int(r['stage'])==stage];assert len(selected)==a.frames
  waits=[float(r['wait_ms']) for r in selected];calls=sum(int(float(r['calls'])) for r in selected);assert calls>0
  report['stages'].append({'stage':stage,'frames':len(selected),'wait_ms_mean':statistics.mean(waits),'wait_ms_p95':percentile(waits,95),'observed_wait_calls':calls,'timeouts':sum(int(float(r['timeouts'])) for r in selected),'message_returns':sum(int(float(r['messages'])) for r in selected),'graphics_nonwait_wall_ms_mean':case['stages'][stage]['graphics_wall_mean_ms']-statistics.mean(waits)})
 assert before=={str(p):sha(p) for p in (exe,dll,a.project/'Data/Scripts.rxdata')}
 report['originals_preserved']=True;report['passed']=True;(out/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print('Pinned original frame-wait observation, refusal and import restoration PASS')

if __name__=='__main__':main()
