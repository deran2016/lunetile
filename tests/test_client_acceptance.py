import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from benchmark_runtime_client import compare,render_accepted,tile_compare,text_composite_compare

class ClientAcceptanceTests(unittest.TestCase):
 def test_output_and_logic_are_independent_gates(self):
  for rate in (40,60,120):
   row=dict(render_rate=rate,logic_fps=120,present_fps=rate,missing_fraction=0)
   self.assertTrue(render_accepted(row))
   for field,value in [('logic_fps',60),('present_fps',rate*.95),('missing_fraction',.03)]:
    self.assertFalse(render_accepted(dict(row,**{field:value})))
 def test_requires_both_time_allocation_and_tail_limits(self):
  rows=[dict(engine=engine,kind='objects',sprites=300,viewports=8,build=build,mean_ms=mean,p95_ms=tail,allocated_per_frame=allocated) for engine in ('xp','vxa') for build,mean,tail,allocated in [('baseline',2,3,1500),('candidate',1,2,500)]]
  self.assertTrue(all(r['passed'] for r in compare(rows)))
  for field,value in [('mean_ms',1.6),('p95_ms',3.2),('allocated_per_frame',1100)]:
   changed=[dict(row) for row in rows];changed[-1][field]=value
   self.assertFalse(compare(changed)[-1]['passed'])
 def test_unique_text_cannot_be_hidden_by_repeated_text_gain(self):
  rows=[dict(engine=engine,kind='text',profile=profile,build=build,mean_ms=mean,p95_ms=mean,allocated_per_call=5) for engine in ('xp','vxa') for profile in ('repeated','unique') for build,mean in [('baseline',1),('candidate',.5)]]
  self.assertTrue(all(r['passed'] for r in compare(rows)))
  rows[-1]['p95_ms']=1.2
  self.assertFalse(compare(rows)[-1]['passed'])

 def test_tile_profiles_keep_independent_thresholds(self):
  rows=[dict(build=label,moving=moving,render_rate=120,total_ms={'mean':total,'p95':total},combined_ms={'mean':combined},parse_ms={'mean':parsed},allocated_per_present=allocated,batches={'tile_quads':100},parse_storage={'tile_used_bytes':used,'tile_reserved_bytes':reserved}) for moving in (False,True) for label,total,combined,parsed,allocated,used,reserved in [('baseline',4,3,.3,6000,16000,16000),('candidate',1,.8,.1,800,36,3600)]]
  for profile in ('xp-tile-cache','vxa-tile-parse'):self.assertTrue(all(r['passed'] for r in tile_compare(rows,profile)))
  rows[-1]['parse_storage']['tile_reserved_bytes']=5000
  self.assertFalse(tile_compare(rows,'vxa-tile-parse')[-1]['passed'])
  self.assertTrue(tile_compare(rows,'xp-tile-cache')[-1]['passed'])

 def test_xp_submit_requires_calls_scene_total_and_tail(self):
  rows=[dict(build=label,moving=moving,render_rate=120,total_ms={'mean':total,'p95':total},allocated_per_present=100,parse_storage={'scene_ms':{'mean':scene}},batches={'tile_draws':draws},tile_reference_quads=1000) for moving in (False,True) for label,total,scene,draws in [('baseline',1,.4,1000),('candidate',.7,.1,1)]]
  self.assertTrue(all(r['passed'] for r in tile_compare(rows,'xp-tile-submit')))
  rows[-1]['batches']['tile_draws']=110
  self.assertFalse(tile_compare(rows,'xp-tile-submit')[-1]['passed'])
 def test_text_composition_has_distinct_engine_and_regression_limits(self):
  rows=[dict(engine=e,profile=p,build=b,mean_ms=m,p95_ms=m,allocated_per_call=a) for e in ('xp','vxa') for p in ('repeated','unique','compressed','plain') for b,m,a in [('baseline',1,60),('candidate',.5,12)]]
  self.assertTrue(all(r['passed'] for r in text_composite_compare(rows)))
  rows[-1]['mean_ms']=1.2
  self.assertFalse(text_composite_compare(rows)[-1]['passed'])
