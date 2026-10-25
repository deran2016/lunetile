import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from benchmark_runtime_client import compare,render_accepted

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
