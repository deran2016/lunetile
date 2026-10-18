"""Three separate GPU/wait diagnostic pairs; primary frame comparisons stay unhooked."""
import argparse,csv,ctypes,json,math,statistics,time
from pathlib import Path
import psutil
from benchmark_runtime import run_case,percentile
from test_runtime import ROOT,ORIGINAL_DLL,ORIGINAL_EXE,sha
from migrate_project import transform
from rxdata import read


def diagnostic_source(probe):
 marker=b"raise 'Missing measured frames' unless write.call('frames.csv')==frames*4"
 if probe.count(marker)!=1:raise ValueError('Owned benchmark write marker changed')
 extra=b"\ntimeline=Win32API.new('RGSSBenchMetrics','BenchWriteTimeline','P','I')\nraise 'Timeline write failed' unless timeline.call('frame-timeline.csv')==frames*4"
 return probe.replace(marker,marker+extra)


def timeline(path,frames):
 with path.open() as stream:rows=list(csv.DictReader(stream))
 result=[]
 assert len(rows)==frames*4
 for index,row in enumerate(rows):
  item={key:int(value) for key,value in row.items()}
  assert item['stage']==index//frames and item['frame']==index
  assert 0<item['start_qpc']<=item['logic_qpc']<=item['end_qpc'] and item['qpc_frequency']>0
  if result:assert result[-1]['end_qpc']<=item['start_qpc']
  result.append(item)
 assert len({r['qpc_frequency'] for r in result})==1
 return result


def parts(folder,frames,engine):
 clocks=timeline(folder/'frame-timeline.csv',frames)
 path=folder/('wait-parts.csv' if engine=='original' else 'render-parts.csv')
 with path.open() as stream:rows=list(csv.DictReader(stream))
 assert len(rows)==frames*4
 result=[]
 for stage in range(4):
  selected=[r for r in rows if int(r['stage'])==stage]
  assert len(selected)==frames and [int(r['frame']) for r in selected]==list(range(80,frames+80))
  waits=[float(row['wait_ms']) for row in selected];assert all(math.isfinite(v) and v>=0 for v in waits)
  times=clocks[stage*frames:(stage+1)*frames]
  result.append({'stage':stage,'frames':frames,'wait_mean_ms':statistics.mean(waits),
                 'wait_ms':{str(p):percentile(waits,p) for p in (50,95,99)},
                 'measured_start_qpc':times[0]['start_qpc'],'measured_end_qpc':times[-1]['end_qpc'],
                 'qpc_frequency':times[0]['qpc_frequency']})
 return result


def recorder(trace):
 identity=json.loads((trace/'recording.json').read_text(encoding='utf-8-sig'))
 process=psutil.Process(identity['recorder_pid'])
 assert process.is_running() and abs(process.create_time()-identity['recorder_creation_unix'])<.01
 assert process.name().lower() in ('powershell.exe','pwsh.exe')
 assert identity['start_exit_code']==0 and identity['profile_sha256']==sha(ROOT/'tests/runtime_gpu_trace.wprp')
 assert not (trace/'session-result.json').exists(),'Recorder already stopped'
 return identity


def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ('project','fixture','original','dll','trace','output'):ap.add_argument(name,type=Path)
 ap.add_argument('--frames',type=int,default=400);a=ap.parse_args()
 assert 60<=a.frames<=1800
 assert not ctypes.WinDLL('shell32').IsUserAnAdmin(),'The game controller must not run as administrator'
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);trace=a.trace.resolve()
 exe=(a.project/'Game.exe').resolve();old=a.original.resolve();new=a.dll.resolve()
 assert sha(exe)==ORIGINAL_EXE and sha(old)==ORIGINAL_DLL and sha(new)!=ORIGINAL_DLL
 originals={str(p):sha(p) for p in (exe,old,a.project/'Data/Scripts.rxdata')}
 identity=recorder(trace)
 metrics=ROOT/'build/runtime-native/bin/Release/RGSSBenchMetrics.dll'
 observer=ROOT/'build/runtime-native/bin/Release/RGSSWaitObserver.dll'
 report={'passed':False,'runtime_sha256':sha(new),'metrics_sha256':sha(metrics),'observer_sha256':sha(observer),
         'trace_instance':identity['instance'],'frames_per_stage':a.frames,'pairs':[],
         'scope':'Separate instrumented three pairs: pinned original wait import observation versus replacement scheduler wall partitions, plus absolute-QPC joins to a private WPR trace. Primary unhooked performance pairs remain separate. Raw ETL and stock script data must remain private. Original GPU attribution requires offline validation and is not assumed from these frame or wait measurements.'}
 try:
  entries=read((a.project/'Data/Scripts.rxdata').read_bytes());patches,_=transform(entries)
  probe=diagnostic_source((ROOT/'tests/runtime_bench.rb').read_bytes())
  for pair in range(3):
   cases={}
   for engine in (('original','replacement') if pair%2==0 else ('replacement','original')):
    recorder(trace)
    definitions=b'\n'.join(patches.get(i,e.source()) if engine=='replacement' else e.source() for i,e in enumerate(entries[:-1]))
    if engine=='original':
     source=definitions+b'\n'+(ROOT/'tests/runtime_wait_profile.rb').read_bytes()+b'\nbegin\n'+probe+b'\nensure\nWaitProfile.finish\nend\n'
    else:source=definitions+b'\n'+(ROOT/'tests/runtime_render_profile.rb').read_bytes()+b'\n'+probe
    folder=out/(str(pair+1)+'-'+engine)
    case=run_case(a.fixture.resolve(),exe,old if engine=='original' else new,metrics,source,folder,a.frames,
                  gpu=engine=='replacement',extra_modules=(observer,) if engine=='original' else ())
    if engine=='original':assert (folder/'wait-observer-restored.txt').read_text()=='original-import-restored'
    case['parts']=parts(folder,a.frames,engine)
    # Identifies the exact private trace targets without broad Game.exe-name filtering.
    process=json.loads((folder/'process-identity.json').read_text());assert process['launcher_sha256']==ORIGINAL_EXE
    case['pid']=process['pid'];case['creation_unix']=process['creation_unix']
    assert case['dll_sha256']==(ORIGINAL_DLL if engine=='original' else report['runtime_sha256'])
    assert sha(metrics)==report['metrics_sha256'] and sha(observer)==report['observer_sha256']
    cases[engine]=case
   assert cases['original']['oracle']==cases['replacement']['oracle']
   report['pairs'].append(cases)
  recorder(trace);assert originals=={str(p):sha(Path(p)) for p in originals}
  report['originals_preserved']=True;report['passed']=True
 finally:
  (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
  (trace/'stop.requested').write_text('Component controller finished; stop only its private instance\n')
 print('Three diagnostic pairs, wait restoration, absolute clocks and original preservation: PASS')


if __name__=='__main__':main()
