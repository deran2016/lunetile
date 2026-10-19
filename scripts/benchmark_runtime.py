"""Paired, rendered stock-map benchmark. All original binaries/data stay in isolated copies."""
import argparse,ast,csv,hashlib,json,math,platform,shutil,statistics,subprocess,sys,time
from pathlib import Path
import psutil
from PIL import Image,ImageDraw
from test_runtime import ROOT,sha,scripts,ORIGINAL_EXE,ORIGINAL_DLL
from migrate_project import transform
from rxdata import read

def percentile(values,p):
 values=sorted(values);position=(len(values)-1)*p/100;low=int(position);high=min(low+1,len(values)-1)
 return values[low]+(values[high]-values[low])*(position-low)

def assets(root):
 tiles=root/'Graphics/Tilesets';chars=root/'Graphics/Characters';tiles.mkdir(parents=True);chars.mkdir(parents=True)
 image=Image.new('RGBA',(256,32),(35,100,55,255));draw=ImageDraw.Draw(image)
 for x in range(0,256,32):draw.rectangle((x+2,2,x+29,29),outline=(90,160,70,255),width=2)
 draw.rectangle((32,0,63,31),fill=(130,70,140,170));image.save(tiles/'Benchmark.png')
 image=Image.new('RGBA',(192,256),(0,0,0,0));draw=ImageDraw.Draw(image)
 for y in range(4):
  for x in range(4):draw.rectangle((x*48+9,y*64+8,x*48+38,y*64+62),fill=(90+x*35,80+y*35,190,240))
 image.save(chars/'BenchActor.png')

def run_case(base,exe,dll,metrics,source,out,frames,gpu=False,gpu_engine=False,extra_modules=()):
 library='RGSS104E.dll' if sha(dll)==ORIGINAL_DLL else 'Lunetile.dll'
 out.mkdir();shutil.copy2(exe,out/'Game.exe');shutil.copy2(dll,out/library);shutil.copy2(metrics,out/metrics.name)
 for module in extra_modules:shutil.copy2(module,out/module.name)
 runtime_hash=sha(out/library);metrics_hash=sha(out/metrics.name)
 shutil.copytree(base/'Data',out/'Data');shutil.copytree(base/'Graphics',out/'Graphics')
 (out/'Scripts.rxdata').write_bytes(scripts(source));(out/'bench-frames.txt').write_text(str(frames))
 if gpu:(out/'bench-gpu.txt').write_text('Diagnostic only; not paired primary timings')
 (out/'Game.ini').write_text(f'[Game]\nLibrary={library}\nScripts=Scripts.rxdata\nTitle=RGSSXP rendered benchmark\nRTP1=\nRTP2=\nRTP3=\n')
 process=subprocess.Popen([str(out/'Game.exe')],cwd=out)
 print(f'RUN {out.name} pid={process.pid}',flush=True)
 began=time.monotonic();modules={};memory=[];counter=None;gpu_samples=[];next_gpu=0;last_phase=None;phase_started=began
 try:
  (out/'process-identity.json').write_text(json.dumps({'pid':process.pid,'creation_unix':psutil.Process(process.pid).create_time(),'executable':str(out/'Game.exe'),'launcher_sha256':sha(out/'Game.exe')},indent=2)+'\n')
  if gpu_engine:
   from gpu_counter import GpuCounter
   counter=GpuCounter(process.pid)
  while process.poll() is None:
   if time.monotonic()-began>90+frames*4/40*3:raise TimeoutError('Rendered benchmark exceeded bounded duration')
   try:
    target=psutil.Process(process.pid);info=target.memory_info();memory.append([time.monotonic()-began,info.private,info.rss])
    if not any(Path(name).name.lower()==metrics.name.lower() for name in modules) and time.monotonic()-began>0.8:
     modules={item.path:sha(Path(item.path)) for item in target.memory_maps() if Path(item.path).suffix.lower() in ('.exe','.dll') and Path(item.path).is_file()}
   except psutil.NoSuchProcess:pass
   if counter and time.monotonic()>=next_gpu:
    progress=out/'bench-progress.txt'
    def phase():
     try:return int(progress.read_text().strip())
     except (FileNotFoundError,ValueError):return None
    before_phase=phase();now=time.monotonic()
    if before_phase!=last_phase:phase_started=now;last_phase=before_phase
    sample=counter.sample();sample.update({'time_s':now-began,'phase_before':before_phase,'phase_after':phase(),'phase_age_s':now-phase_started})
    gpu_samples.append(sample);next_gpu=time.monotonic()+1
   time.sleep(.2)
 finally:
  if process.poll() is None:process.terminate();process.wait()
  if counter:counter.close()
  if gpu_engine:(out/'gpu-engines.json').write_text(json.dumps(gpu_samples,indent=2))
  (out/'modules.json').write_text(json.dumps(modules,indent=2));(out/'memory.json').write_text(json.dumps(memory))
 assert process.returncode==0 and (out/'runtime-complete.txt').is_file(),{'exit':process.returncode,'case':str(out)}
 assert sha(out/library)==runtime_hash and sha(out/metrics.name)==metrics_hash
 assert runtime_hash in modules.values() and metrics_hash in modules.values(),'Expected modules were not sampled'
 assert all(sha(out/module.name) in modules.values() for module in extra_modules),'Diagnostic module was not sampled'
 if runtime_hash!=ORIGINAL_DLL:assert ORIGINAL_DLL not in modules.values(),'Original runtime loaded in replacement case'
 assert not any(Path(name).name.lower()=='rgssframepacing.dll' for name in modules)
 rows=list(csv.DictReader((out/'frames.csv').open()))
 assert len(rows)==frames*4
 result={'dll_sha256':runtime_hash,'measurement_sha256':metrics_hash,'script_archive_sha256':sha(out/'Scripts.rxdata'),'frames_per_stage':frames,'instrumentation_triplet_us':float((out/'instrumentation.txt').read_text()),'stages':[],'oracle':ast.literal_eval((out/'oracle.txt').read_text()),'graphics_modules':[Path(name).name for name in modules if any(word in name.lower() for word in ('d3d','ddraw','nvwg','atid','atic'))]}
 for stage in range(4):
  selected=[row for row in rows if int(row['stage'])==stage]
  assert len(selected)==frames
  assert all(row['active_start']=='1' and row['active_end']=='1' for row in selected),'Measured frame was not foreground; do not silently filter/reuse it'
  intervals=[float(row['interval_ms']) for row in selected]
  result['stages'].append({'stage':stage,'frames':len(selected),'interval_ms':{str(p):percentile(intervals,p) for p in (50,95,99)},'long_37_5ms':sum(v>37.5 for v in intervals),'long_50ms':sum(v>50 for v in intervals),'logic_wall_mean_ms':statistics.mean(float(row['logic_wall_ms']) for row in selected),'graphics_wall_mean_ms':statistics.mean(float(row['graphics_wall_ms']) for row in selected),'logic_cpu_mean_ms':statistics.mean(float(row['logic_cpu_ms']) for row in selected),'graphics_cpu_mean_ms':statistics.mean(float(row['graphics_cpu_ms']) for row in selected),'process_cpu_mean_ms':statistics.mean(float(row['process_cpu_ms']) for row in selected)})
 (out/'summary.json').write_text(json.dumps(result,indent=2));return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);ap.add_argument('original_dll',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('output',type=Path)
 ap.add_argument('--frames',type=int,default=400);ap.add_argument('--pairs',type=int,default=3);ap.add_argument('--gpu-diagnostic',action='store_true')
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 assert 60<=a.frames<=1800 and 1<=a.pairs<=5
 exe=(a.project/'Game.exe').resolve();original=a.original_dll.resolve();dll=a.dll.resolve();metrics=ROOT/'build/runtime-native/bin/Release/RGSSBenchMetrics.dll'
 assert sha(exe)==ORIGINAL_EXE and sha(original)==ORIGINAL_DLL and sha(dll)!=ORIGINAL_DLL
 before={str(p):sha(p) for p in (exe,original,a.project/'Data/Scripts.rxdata')}
 command=[sys.executable,str(ROOT/'scripts/probe_original_types.py'),str(exe),str(original),str(out/'fixture'),'--probe',str(ROOT/'tests/rgss_bench_fixture.rb'),'--data',str((a.project/'Data').resolve())]
 with (out/'fixture.log').open('w') as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
 assets(out/'fixture')
 entries=read((a.project/'Data/Scripts.rxdata').read_bytes());replacements,_=transform(entries)
 selected=[(i,e) for i,e in enumerate(entries[:-1])]
 probe=(ROOT/'tests/runtime_bench.rb').read_bytes()
 sources={'original':b'\n'.join(e.source() for i,e in selected)+b'\n'+probe,'replacement':b'\n'.join(replacements.get(i,e.source()) for i,e in selected)+b'\n'+probe}
 report={'passed':False,'frames_per_stage':a.frames,'pairs':[],'fixture_stages':['0 stationary','100 stationary / 10 parallel','300 stationary / 30 parallel','300 route-moving / 30 parallel'],'dll_sha256':sha(dll),'original_sha256':sha(original),'measurement_sha256':sha(metrics),'scope':'Own rendered 40x30 map and images; stock map/player/interpreter/sprites; 640x480 and 40Hz. Per-frame CPU counters are quantized; only stage averages are meaningful. Graphics wall includes render and wait, not exact frame-wait duration. No original GPU execution timing in this report.'}
 try:
  for pair in range(a.pairs):
   cases={}
   for engine in (('original','replacement') if pair%2==0 else ('replacement','original')):
    cases[engine]=run_case(out/'fixture',exe,original if engine=='original' else dll,metrics,sources[engine],out/(str(pair+1)+'-'+engine),a.frames)
    assert cases[engine]['dll_sha256']==(report['original_sha256'] if engine=='original' else report['dll_sha256']) and cases[engine]['measurement_sha256']==report['measurement_sha256'],'A build changed during the paired capture'
   assert cases['original']['oracle']==cases['replacement']['oracle'],'Different logical state; timings cannot be treated as equivalent gameplay'
   report['pairs'].append(cases)
  if a.gpu_diagnostic:report['gpu_diagnostic']=run_case(out/'fixture',exe,dll,metrics,sources['replacement'],out/'gpu-diagnostic',a.frames,True)
  assert before=={str(p):sha(p) for p in (exe,original,a.project/'Data/Scripts.rxdata')}
  report['originals_preserved']=True;report['passed']=True
 finally:(out/'summary.json').write_text(json.dumps(report,indent=2))
 print('Rendered pairs, foreground checks, logical-state parity, metrics and original preservation PASS',flush=True)

if __name__=='__main__':main()
