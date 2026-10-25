import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from benchmark_runtime_browser import compare

class BrowserAcceptanceTests(unittest.TestCase):
 def rows(self):
  return [dict(engine=e,moving=m,render_rate=120,build=b,browser_open=False,total_ms={'mean':1.0,'p95':2.0}) for e in ('xp','vxa') for m in (False,True) for b in ('baseline','candidate')]
 def test_unused_browser_mean_and_p95_both_gate_each_engine_and_motion(self):
  rows=self.rows();self.assertTrue(all(c['passed'] for c in compare(rows)))
  rows[-1]['total_ms']['p95']=2.11
  result=compare(rows);self.assertFalse(result[-1]['passed']);self.assertTrue(all(c['passed'] for c in result[:-1]))
  rows[-1]['total_ms']['p95']=2.0;rows[-1]['total_ms']['mean']=1.051
  self.assertFalse(compare(rows)[-1]['passed'])
 def test_open_panel_and_other_output_rates_do_not_change_unused_cpu_gate(self):
  rows=self.rows();rows.extend(dict(r,browser_open=True,total_ms={'mean':9.0,'p95':15.0}) for r in list(rows))
  rows.extend(dict(r,render_rate=40,total_ms={'mean':9.0,'p95':15.0}) for r in list(rows))
  self.assertTrue(all(c['passed'] for c in compare(rows)))
