"""Summarize already captured rendered pairs; keep frame intervals, CPU and GPU scopes distinct."""
import argparse,csv,json,statistics
from pathlib import Path
from benchmark_runtime import percentile

def summarize(root):
 report=json.loads((root/'summary.json').read_text());assert report['passed']
 pairs=report['pairs'];assert len(pairs)>=3,'Performance criterion requires at least three pairs'
 result={'dll_sha256':report['dll_sha256'],'original_sha256':report['original_sha256'],'pairs':len(pairs),'frames_per_stage_per_pair':report['frames_per_stage'],'stages':[],'scope':report['scope']}
 for stage in range(4):
  old=[pair['original']['stages'][stage] for pair in pairs];new=[pair['replacement']['stages'][stage] for pair in pairs]
  ratios=[b['interval_ms']['95']/a['interval_ms']['95'] for a,b in zip(old,new)]
  item={'stage':stage,'scenario':report['fixture_stages'][stage],'p95_ms_original_median':statistics.median(x['interval_ms']['95'] for x in old),'p95_ms_replacement_median':statistics.median(x['interval_ms']['95'] for x in new),'p95_change_percent_pairs':[(ratio-1)*100 for ratio in ratios],'repeated_over_5_percent_regression':sum(ratio>1.05 for ratio in ratios)>=2}
  for name,values in [('original',old),('replacement',new)]:
   item[name]={'logic_cpu_mean_ms_median':statistics.median(x['logic_cpu_mean_ms'] for x in values),'graphics_cpu_mean_ms_median':statistics.median(x['graphics_cpu_mean_ms'] for x in values),'process_cpu_mean_ms_median':statistics.median(x['process_cpu_mean_ms'] for x in values),'long_37_5ms_total':sum(x['long_37_5ms'] for x in values),'long_50ms_total':sum(x['long_50ms'] for x in values)}
   item[name]['interval_ms_medians']={str(p):statistics.median(x['interval_ms'][str(p)] for x in values) for p in (50,95,99)}
  result['stages'].append(item)
 result['no_repeated_general_p95_regression']=not any(x['repeated_over_5_percent_regression'] for x in result['stages'][:3])
 result['instrumentation_triplet_us']={name:[pair[name]['instrumentation_triplet_us'] for pair in pairs] for name in ('original','replacement')}
 gpu=root/'gpu-diagnostic/gpu.csv'
 if gpu.exists():
  rows=list(csv.reader(gpu.open()));result['replacement_gpu_diagnostic']=[]
  for stage in range(4):
   values=[float(row[3]) for row in rows if int(row[0])==stage and row[3] and float(row[6])==0]
   result['replacement_gpu_diagnostic'].append({'stage':stage,'unique_results':len(values),'gpu_ms':{str(p):percentile(values,p) for p in (50,95,99)} if values else None})
  result['gpu_scope']='Separate instrumented run; async D3D11 timestamps, deduplicated by completed render sequence; excludes frames with focus pauses. No original GPU execution-time comparison.'
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('capture',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
 result=summarize(a.capture);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
