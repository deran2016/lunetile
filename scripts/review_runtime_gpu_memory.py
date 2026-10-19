"""Review completed, process-bound GPU memory samples; never interpret missing data as zero."""
import argparse,json,math,statistics
from pathlib import Path
from test_runtime import sha,ORIGINAL_DLL


def review(project):
 boot=json.loads((project/'boot-result.json').read_text())
 assert boot['passed'] and boot['endurance']['meets_duration_and_roundtrip_gate']
 assert boot['dll_sha256']==sha(project/'Lunetile.dll')!=ORIGINAL_DLL
 images=json.loads((project/'modules.json').read_text())
 assert boot['dll_sha256'] in images.values() and ORIGINAL_DLL not in images.values()
 identity=json.loads((project/'gpu-memory-identity.json').read_text(encoding='utf-8-sig'))
 expected=(identity['pid'],identity['creation_ticks'])
 assert expected[0]>0 and expected[1]>0
 assert Path(identity['exe']).resolve()==(project/'Game.exe').resolve()
 source=project/'gpu-memory-snapshots.jsonl'
 rows=[json.loads(line) for line in source.read_text(encoding='utf-8-sig').splitlines()]
 points=[];unavailable=0;before_progress=0
 for row in rows:
  assert (row['pid'],row['creation_ticks'])==expected,'Process identity changed'
  if not row.get('available'):
   unavailable+=1;continue
  assert row['rows'] and all(item['Name'].startswith(f'pid_{expected[0]}_') for item in row['rows'])
  point={}
  for key in ('DedicatedUsage','SharedUsage','TotalCommitted'):
   values=[item[key] for item in row['rows']]
   assert all(isinstance(value,int) and value>=0 for value in values),'Invalid GPU memory counter'
   point[key]=sum(values)
  active=row.get('active_seconds')
  if active is None:
   before_progress+=1;continue
  assert math.isfinite(active) and active>=0
  point['active_seconds']=active;points.append(point)
 assert len(points)>=50 and points[-1]['active_seconds']>=1770,'Incomplete GPU coverage'
 assert all(0<b['active_seconds']-a['active_seconds']<=65 for a,b in zip(points,points[1:])),'GPU sample gap or active-time reset'
 steady=[row for row in points if row['active_seconds']>=600]
 assert len(steady)>=30
 x=statistics.mean(row['active_seconds'] for row in steady)
 denominator=sum((row['active_seconds']-x)**2 for row in steady)
 metrics={}
 for key in ('DedicatedUsage','SharedUsage','TotalCommitted'):
  y=statistics.mean(row[key] for row in steady)
  slope=sum((row['active_seconds']-x)*(row[key]-y) for row in steady)/denominator*60/1048576
  metrics[key]={'minimum_bytes':min(row[key] for row in points),'maximum_bytes':max(row[key] for row in points),
                'steady_first_three_median_bytes':statistics.median(row[key] for row in steady[:3]),
                'steady_last_three_median_bytes':statistics.median(row[key] for row in steady[-3:]),
                'steady_slope_mib_per_minute':slope}
 return {'measurement_valid':True,'dll_sha256':boot['dll_sha256'],'process_identity':list(expected),
         'samples':len(points),'unavailable_samples':unavailable,'samples_before_progress':before_progress,
         'first_active_seconds':points[0]['active_seconds'],'last_active_seconds':points[-1]['active_seconds'],
         'metrics':metrics,'input_sha256':sha(source),'identity_sha256':sha(project/'gpu-memory-identity.json'),
         'analysis_sha256':sha(Path(__file__)),
         'scope':'Completed owned PID/creation-time bound Windows GPU memory samples; adapter rows summed. Full range and post-600s trend; unavailable data excluded and counted. Not GPU frame timing or proof that every allocation is leak-free.'}


def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('project',type=Path);a=ap.parse_args()
 project=a.project.resolve();result=review(project)
 with (project/'gpu-memory-review.json').open('x') as stream:json.dump(result,stream,indent=2)
 print('Completed GPU memory coverage and process identity: PASS')


if __name__=='__main__':main()
