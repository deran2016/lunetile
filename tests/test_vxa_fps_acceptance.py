import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from benchmark_runtime_vxa import accepted,reductions,unbatchable_comparison

class VXAFPSAcceptanceTests(unittest.TestCase):
 def test_unbatchable_scene_must_not_regress(self):
  rows=[{'build':label,'scenario':'alternating','repeat':0,'total_ms':{'mean':total,'p95':total*1.5},'submit_ms':{'mean':total/2}} for label,total in [('baseline',1.0),('optimized',1.02)]]
  self.assertTrue(unbatchable_comparison(rows)['passed'])
  rows[-1]['total_ms']['mean']=1.1
  self.assertFalse(unbatchable_comparison(rows)['passed'])
  rows[-1]['total_ms']={'mean':1.0,'p95':2.0}
  self.assertFalse(unbatchable_comparison(rows)['passed'])
 def test_d3d_profile_measures_submit_total_and_each_repeat_p95(self):
  import copy
  rows=[]
  for moving in (False,True):
   for repeat in range(3):
    for label in ('baseline','optimized'):
     new=label=='optimized'
     rows.append({'build':label,'moving':moving,'repeat':repeat,'render_rate':120,
      'combined_ms':{'mean':.56},'submit_ms':{'mean':.2 if new else .58},
      'total_ms':{'mean':.76 if new else 1.14,'p95':1 if new else 1.5},
      'allocated_per_present':520 if new else 517,
      'batches':{'tile_quads':3900,'tile_draws':1,'instance_maps':1}})
  self.assertTrue(all(r['passed'] for r in reductions(rows,'tile-d3d')))
  self.assertFalse(any(r['passed'] for r in reductions(rows)))
  for field,value in [('submit_ms',{'mean':.58}),('total_ms',{'mean':1.14,'p95':1.5}),
                      ('total_ms',{'mean':.76,'p95':2}),('allocated_per_present',2000),
                      ('batches',{'tile_quads':3900,'tile_draws':1000,'instance_maps':1}),
                      ('batches',{'tile_quads':3900,'tile_draws':1,'instance_maps':2})]:
   changed=copy.deepcopy(rows)
   for row in changed:
    if row['build']=='optimized' and row['moving']:row[field]=value
   self.assertFalse(reductions(changed,'tile-d3d')[1]['passed'],field)
  rows[-1]['total_ms']['p95']=2
  self.assertFalse(reductions(rows,'tile-d3d')[1]['passed'])
 def test_requires_cpu_and_allocation_reductions(self):
  rows=[]
  for moving in (False,True):
   for label,cpu,allocated in [('baseline',2.7,4000),('optimized',1.8,1000)]:
    rows.append({'build':label,'moving':moving,'render_rate':120,'combined_ms':{'mean':cpu},'allocated_per_present':allocated})
  self.assertTrue(all(r['passed'] for r in reductions(rows)))
  rows[-1]['allocated_per_present']=3000
  self.assertFalse(reductions(rows)[1]['passed'])
  rows[-1]['allocated_per_present']=1000;rows[-1]['combined_ms']['mean']=2.5
  self.assertFalse(reductions(rows)[1]['passed'])
 def test_rejects_fast_logic_with_slow_output(self):
  row={'render_rate':120,'logic_fps':120,'present_fps':43,'missing_fraction':.64,'command_ms':{'p95':19.3}}
  self.assertFalse(accepted(row))
  row.update(present_fps=120,missing_fraction=0,command_ms={'p95':3.2})
  self.assertTrue(accepted(row))
 def test_each_output_rate_needs_real_time_logic_and_low_command_cost(self):
  for rate in (40,60,120):
   row={'render_rate':rate,'logic_fps':120,'present_fps':rate,'missing_fraction':0,'command_ms':{'p95':3.5}}
   self.assertTrue(accepted(row))
   self.assertFalse(accepted(dict(row,logic_fps=60)))
   self.assertFalse(accepted(dict(row,missing_fraction=.03)))
   self.assertFalse(accepted(dict(row,command_ms={'p95':5})))

if __name__=='__main__':unittest.main()
