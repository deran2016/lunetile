"""Validate separate diagnostic pairs without turning missing GPU attribution into zero."""
import argparse,bisect,csv,json,math,statistics
from collections import Counter
from pathlib import Path
from benchmark_runtime import percentile
from benchmark_runtime_components import timeline,parts


def distribution(values):
 assert values and all(math.isfinite(v) and v>=0 for v in values)
 return {'samples':len(values),'mean_ms':statistics.mean(values),
         'ms':{str(p):percentile(values,p) for p in (50,95,99)},'max_ms':max(values)}


def join_presents(rows,clocks,pid):
 starts=[r['start_qpc'] for r in clocks];joined={};previous=0
 for row in rows:
  assert int(row['ProcessID'])==pid
  qpc=int(row['QPCTime']);assert qpc>previous;previous=qpc
  index=bisect.bisect_right(starts,qpc)-1
  if index<0 or not clocks[index]['logic_qpc']<=qpc<=clocks[index]['end_qpc']:continue
  assert index not in joined,'Multiple presents in one measured graphics interval'
  value=float(row['msGPUActive']);assert math.isfinite(value) and value>=0
  joined[index]=row
 assert len(joined)==len(clocks),'Incomplete present attribution; do not interpolate missing frames'
 return joined


def timestamp_samples(rows,frames):
 assert len(rows)==frames*4
 result=[];previous_current=previous_completed=-1
 for stage in range(4):
  selected=rows[stage*frames:(stage+1)*frames]
  assert all(len(r)==7 and int(r[0])==stage for r in selected)
  sequence_to_frame={int(r[1])-1:stage*frames+i for i,r in enumerate(selected)}
  assert len(sequence_to_frame)==frames
  samples=[]
  for row in selected:
   current,completed=int(row[1]),int(row[2]);value=float(row[3])
   assert current>previous_current and completed>previous_completed and completed<current
   assert int(row[4])>0 and int(row[5])==0 and float(row[6])==0
   assert math.isfinite(value) and value>=0
   previous_current,previous_completed=current,completed
   if completed in sequence_to_frame:samples.append((sequence_to_frame[completed],value))
  assert samples and len({i for i,_ in samples})==len(samples)
  result.append({'stage':stage,'observations':frames,'measured_frame_samples':len(samples),
                 'outside_measured_window':frames-len(samples),'samples':samples})
 return result


def review(capture,pm,etw):
 source=json.loads((capture/'summary.json').read_text());frames=source['frames_per_stage']
 assert source['passed'] and source['originals_preserved'] and len(source['pairs'])==3
 result={'passed':True,'validation_scope':'Diagnostic acquisition and attribution checks only; not full-plan acceptance',
         'runtime_sha256':source['runtime_sha256'],'frames_per_stage':frames,'pairs':[],
         'original_gpu_execution_ms':None,'gpu_speedup':None,
         'scope':'Three separate instrumented diagnostic pairs. Wait is elapsed wall time, not CPU time. Replacement D3D11 timestamps cover render commands before Present; PresentMon msGPUActive is a separate scheduling-derived estimate. Missing original GPU attribution stays unknown. Primary unhooked frame comparisons are separate.'}
 for index,pair in enumerate(source['pairs'],1):
  output={}
  for engine in ('original','replacement'):
   name=f'{index}-{engine}';folder=capture/name;case=pair[engine]
   clocks=timeline(folder/'frame-timeline.csv',frames)
   identity=json.loads((folder/'process-identity.json').read_text());assert identity['pid']==case['pid'] and identity['creation_unix']==case['creation_unix']
   actual_parts=parts(folder,frames,engine);assert actual_parts==case['parts']
   analyzed=json.loads((pm/name/'process-result.json').read_text());assert analyzed['exit_code']==0 and analyzed['pid']==case['pid']
   assert (pm/name/'frames.csv').exists()==analyzed['csv_exists']
   entry={'stages':actual_parts,'presentmon_csv_exists':analyzed['csv_exists']}
   joined=None
   if analyzed['csv_exists']:
    with (pm/name/'frames.csv').open() as stream:rows=list(csv.DictReader(stream))
    joined=join_presents(rows,clocks,case['pid'])
    entry['presentmon_stages']=[]
    for stage in range(4):
     selected=[joined[i] for i in range(stage*frames,(stage+1)*frames)]
     entry['presentmon_stages'].append({'stage':stage,'gpu_active_estimate':distribution([float(r['msGPUActive']) for r in selected]),
         'dropped':sum(int(r['Dropped']) for r in selected),'modes':dict(Counter(r['PresentMode'] for r in selected))})
   if engine=='replacement':
    assert joined is not None
    with (folder/'gpu.csv').open() as stream:gpu=timestamp_samples(list(csv.reader(stream)),frames)
    entry['timestamp_stages']=[]
    for stage in gpu:
     entry['timestamp_stages'].append({k:v for k,v in stage.items() if k!='samples'}|{
        'render_commands':distribution([v for _,v in stage['samples']]),
        'presentmon_same_frames':distribution([float(joined[i]['msGPUActive']) for i,_ in stage['samples']])})
   else:
    with (etw/name/'extract.txt').open() as stream:events=[json.loads(line) for line in stream]
    header,end=events[0],events[-1]
    assert header['pid']==case['pid'] and header['frequency']==clocks[0]['qpc_frequency']
    assert header['events_lost']==header['buffers_lost']==end['status']==end['schema_failures']==end['property_failures']==0
    spans=[];pending={}
    for row in events:
     if row['kind']!='gpu' or row['id'] not in (450,451):continue
     key=(row['values']['hHwQueue'],row['values']['ProgressFenceValue'])
     if row['id']==450:
      assert key not in pending;pending[key]=row['qpc']
     elif key in pending:
      start=pending.pop(key);assert row['qpc']>=start;spans.append((start,row['qpc']))
    stage_overlaps=[sum(start<part['measured_end_qpc'] and end>part['measured_start_qpc'] for start,end in spans) for part in actual_parts]
    entry['etw']={'events':end['events'],'events_lost':header['events_lost'],'buffers_lost':header['buffers_lost'],
        'matched_dma_envelopes':len(spans),'unmatched_dma_starts':len(pending),'dma_envelopes_overlapping_stages':stage_overlaps,
        'exact_gpu_execution_ms':None,
        'limitation':'DMA envelopes are submission-to-completion, not execution. No PresentMon frame CSV; absent attributable work is not proof of zero GPU or compositor cost. Header PID on interrupt events alone is not process attribution.'}
   output[engine]=entry
  result['pairs'].append(output)
 result['gpu_comparison_available']=all(p['original']['presentmon_csv_exists'] for p in result['pairs'])
 result['stage_medians']=[]
 for stage in range(4):
  result['stage_medians'].append({'stage':stage,
   'original_wait_mean_ms':statistics.median(p['original']['stages'][stage]['wait_mean_ms'] for p in result['pairs']),
   'replacement_wait_mean_ms':statistics.median(p['replacement']['stages'][stage]['wait_mean_ms'] for p in result['pairs']),
   'replacement_render_gpu_p95_ms':statistics.median(p['replacement']['timestamp_stages'][stage]['render_commands']['ms']['95'] for p in result['pairs']),
   'replacement_presentmon_gpu_p95_ms':statistics.median(p['replacement']['presentmon_stages'][stage]['gpu_active_estimate']['ms']['95'] for p in result['pairs'])})
 return result


if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ('capture','presentmon','etw','output'):ap.add_argument(name,type=Path)
 a=ap.parse_args();assert not a.output.exists(),'Refusing existing review output'
 result=review(a.capture,a.presentmon,a.etw);a.output.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'passed':result['passed'],'pairs':len(result['pairs']),'original_gpu_execution_ms':result['original_gpu_execution_ms'],'stage_medians':result['stage_medians']}))
