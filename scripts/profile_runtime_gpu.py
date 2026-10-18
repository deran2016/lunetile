"""Separate PID-scoped GPU engine diagnostic, including original DirectDraw; not frame latency."""
import argparse,json,statistics
from pathlib import Path
from benchmark_runtime import run_case
from test_runtime import ROOT
from rxdata import read
from migrate_project import transform

def summarize(samples):
 result=[]
 for phase in range(4):
  work=wall=0;counts=0;cost=[];instances=set();excluded=0
  for previous,sample in zip(samples,samples[1:]):
   # Both endpoints must be past the two-second warmup and inside the same phase.
   if not all(row['phase_before']==row['phase_after']==phase and row['phase_age_s']>=2 for row in (previous,sample)):continue
   # Reject both endpoints of a mismatched numerator, without inventing a tolerance or value.
   valid_before={row['instance'] for row in previous['engines'] if row['unit_crosscheck']}
   engines=[row for row in sample['engines'] if row['delta_ms'] is not None]
   if any(not row['unit_crosscheck'] or row['instance'] not in valid_before for row in engines):
    excluded+=1;continue
   if not engines:continue
   interval=statistics.median(row['interval_ms'] for row in engines)
   assert interval>0
   work+=sum(row['delta_ms'] for row in engines);wall+=interval;counts+=1
   cost.append(sample['sample_cost_ms']);instances.update(row['instance'] for row in engines)
  result.append({'stage':phase,'intervals':counts,'excluded_unverified_intervals':excluded,'observed_wall_ms':wall,'engine_work_ms':work,'engine_work_percent_of_wall':100*work/wall if wall else None,'counter_cost_ms_mean':statistics.mean(cost) if cost else None,'instances':sorted(instances)})
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);ap.add_argument('fixture',type=Path);ap.add_argument('original_dll',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('output',type=Path)
 ap.add_argument('--frames',type=int,default=320);a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 entries=read((a.project/'Data/Scripts.rxdata').read_bytes());patches,_=transform(entries)
 report={'scope':'Separate instrumented runs. PID-specific GPU Engine Running Time / utilization numerator in 100 ns units. Sum of engine work may overlap; not GPU frame time or presentation latency. Warmup and cross-phase intervals excluded; lost/reset instance tails are not inferred.','cases':{}}
 for engine,dll in [('original',a.original_dll),('replacement',a.dll)]:
  source=b'\n'.join(patches.get(i,e.source()) if engine=='replacement' else e.source() for i,e in enumerate(entries[:-1]))+b'\n'+(ROOT/'tests/runtime_bench.rb').read_bytes()
  case=run_case(a.fixture.resolve(),(a.project/'Game.exe').resolve(),dll.resolve(),ROOT/'build/runtime-native/bin/Release/RGSSBenchMetrics.dll',source,out/engine,a.frames,gpu_engine=True)
  samples=json.loads((out/engine/'gpu-engines.json').read_text());case['gpu_engines']=summarize(samples)
  assert all(row['intervals']>=3 for row in case['gpu_engines']),'Insufficient continuous PID-scoped GPU observations'
  report['cases'][engine]=case
 assert report['cases']['original']['oracle']==report['cases']['replacement']['oracle']
 report['passed']=True;(out/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print('Original/replacement PID-scoped GPU engine diagnostic PASS')

if __name__=='__main__':main()
