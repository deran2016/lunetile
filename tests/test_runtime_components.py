import csv,sys,tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from benchmark_runtime_components import diagnostic_source,timeline,parts
from review_runtime_components import join_presents,timestamp_samples,distribution

class ComponentTests(unittest.TestCase):
 def setUp(self):
  root=Path(__file__).resolve().parents[1]/'build/test-components';root.mkdir(parents=True,exist_ok=True)
  self.temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temp.cleanup);self.out=Path(self.temp.name)
  self.rows=[[i//2,i,100+i*10,103+i*10,109+i*10,1000] for i in range(8)]
 def write_timeline(self):
  with (self.out/'frame-timeline.csv').open('w',newline='') as stream:
   writer=csv.writer(stream);writer.writerow(['stage','frame','start_qpc','logic_qpc','end_qpc','qpc_frequency']);writer.writerows(self.rows)
 def test_absolute_clocks_have_complete_ordered_coverage(self):
  self.write_timeline();self.assertEqual(len(timeline(self.out/'frame-timeline.csv',2)),8)
  self.rows[4][2]=1;self.write_timeline()
  with self.assertRaises(AssertionError):timeline(self.out/'frame-timeline.csv',2)
  self.rows[4][2]=140;self.rows[6][5]=2000;self.write_timeline()
  with self.assertRaises(AssertionError):timeline(self.out/'frame-timeline.csv',2)
 def test_wait_percentiles_do_not_become_cpu_or_gpu_time(self):
  self.write_timeline()
  with (self.out/'wait-parts.csv').open('w',newline='') as stream:
   writer=csv.writer(stream);writer.writerow(['stage','frame','wait_ms'])
   writer.writerows([phase,80+frame,2+frame*2] for phase in range(4) for frame in range(2))
  result=parts(self.out,2,'original');self.assertEqual(result[0]['wait_mean_ms'],3)
  self.assertAlmostEqual(result[0]['wait_ms']['95'],3.9)
  self.assertEqual(result[3]['measured_start_qpc'],160)
 def test_owned_probe_change_is_explicitly_rejected(self):
  probe=(Path(__file__).parent/'runtime_bench.rb').read_bytes();changed=diagnostic_source(probe)
  self.assertEqual(changed.count(b'BenchWriteTimeline'),1)
  self.assertLess(changed.index(b"write.call('frames.csv')"),changed.index(b'BenchWriteTimeline'))
  with self.assertRaises(ValueError):diagnostic_source(probe+probe)
  with self.assertRaises(ValueError):diagnostic_source(b'unknown code')
 def test_wpr_profile_enables_only_display_win32k_events(self):
  path=Path(__file__).parent/'runtime_gpu_trace.wprp';providers={p.attrib['Id']:p for p in ET.parse(path).findall('./Profiles/EventProvider')}
  win=providers['RGSSXPWin32k'];self.assertEqual(win.find('EventFilters').attrib['FilterIn'],'true')
  self.assertEqual({int(e.attrib['Value']) for e in win.findall('./EventFilters/EventId')},{201,301})
  self.assertIsNone(win.find('Stacks'))
  self.assertIn('RGSSXPDwm',providers);self.assertIn('RGSSXPD3D9',providers)
 def test_present_join_requires_every_exact_process_frame(self):
  self.write_timeline();clocks=timeline(self.out/'frame-timeline.csv',2)
  rows=[{'ProcessID':'7','QPCTime':str(104+i*10),'msGPUActive':'.2'} for i in range(8)]
  self.assertEqual(len(join_presents(rows,clocks,7)),8)
  with self.assertRaises(AssertionError):join_presents(rows[:-1],clocks,7)
  with self.assertRaises(AssertionError):join_presents(rows,clocks,8)
  duplicate=dict(rows[0],QPCTime='105')
  with self.assertRaises(AssertionError):join_presents(rows[:1]+[duplicate]+rows[1:],clocks,7)
 def test_async_gpu_result_is_assigned_to_rendered_frame(self):
  rows=[[str(stage),str(10+stage*10+i),str(8+stage*10+i),'.1',str(1+stage*2+i),'0','0.0'] for stage in range(4) for i in range(2)]
  result=timestamp_samples(rows,2)
  self.assertEqual(result[0]['samples'],[(0,.1)])
  self.assertEqual(result[3]['samples'],[(6,.1)])
  self.assertEqual(result[0]['outside_measured_window'],1)
  rows[0][5]='1'
  with self.assertRaises(AssertionError):timestamp_samples(rows,2)
 def test_gpu_distribution_rejects_missing_and_invalid_values(self):
  for values in ([],[float('nan')],[-1]):
   with self.assertRaises(AssertionError):distribution(values)
  self.assertAlmostEqual(distribution([.1,.3])['mean_ms'],.2)

if __name__=='__main__':unittest.main()
