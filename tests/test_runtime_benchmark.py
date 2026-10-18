import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from benchmark_runtime import percentile
from gpu_counter import intervals
from profile_runtime_gpu import summarize
from test_runtime_stock_boot import copy_missing,endurance_result

class RuntimeBenchmarkTests(unittest.TestCase):
 def test_endurance_memory_slope_uses_wall_time_during_focus_pauses(self):
  root=Path(__file__).resolve().parents[1]/'build/test-runtime-memory';root.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(dir=root) as directory:
   folder=Path(directory)
   (folder/'endurance-result.txt').write_text('active_seconds=1800\nframes=72000\nroundtrips=100\n')
   samples=[{'wall_seconds':600+i,'active_seconds':600+max(0,i-180),'private_bytes':100*1048576+i*1024,'handles':80} for i in range(400)]
   result=endurance_result(folder,samples,{'owned.dll':'fixture'},1800,100)
   self.assertAlmostEqual(result['memory']['private_slope_mib_per_minute'],60/1024)
   self.assertTrue(result['meets_duration_and_roundtrip_gate'])
   for i,sample in enumerate(samples):sample['private_bytes']=100*1048576+i*1048576
   with self.assertRaises(AssertionError):endurance_result(folder,samples,{'owned.dll':'fixture'},1800,100)
   early_leak=[{'wall_seconds':i,'active_seconds':i,'private_bytes':100*1048576+min(i,600)*1048576/60,'handles':80} for i in range(1801)]
   with self.assertRaises(AssertionError):endurance_result(folder,early_leak,{'owned.dll':'fixture'},1800,100)
 def test_fixture_rtp_never_overwrites_project_assets(self):
  temporary_root=Path(__file__).resolve().parents[1]/'build/test-runtime-assets'
  temporary_root.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(dir=temporary_root) as directory:
   self.assertTrue(Path(directory).resolve().is_relative_to(temporary_root.resolve()))
   source=Path(directory)/'rtp';target=Path(directory)/'project'
   source.write_bytes(b'rtp');target.write_bytes(b'project')
   copy_missing(source,target);self.assertEqual(target.read_bytes(),b'project')
   target.unlink();copy_missing(source,target);self.assertEqual(target.read_bytes(),b'rtp')
 def test_percentiles_interpolate_small_captures(self):
  self.assertEqual(percentile([30,10,20],50),20)
  self.assertAlmostEqual(percentile([10,20],95),19.5)
 def test_gpu_reset_and_instance_tail_are_not_fabricated(self):
  old={'a':(10000,100000,10000),'reset':(100,100000,100)}
  new={'a':(30000,200000,30000),'reset':(50,200000,50),'new':(9,200000,9)}
  rows={row['instance']:row for row in intervals(old,new)}
  self.assertEqual(rows['a']['delta_ms'],2)
  self.assertEqual(rows['a']['percent'],20)
  self.assertIsNone(rows['reset']['delta_ms'])
  self.assertTrue(rows['new']['baseline_only'])
  self.assertEqual(intervals(old,{}),[])
 def test_gpu_summary_excludes_warmup_and_cross_phase(self):
  def sample(phase,age,delta):
   return {'phase_before':phase,'phase_after':phase,'phase_age_s':age,'sample_cost_ms':1,'engines':[{'delta_ms':delta,'interval_ms':1000,'unit_crosscheck':True,'instance':'3D'},{'delta_ms':0,'interval_ms':1000,'unit_crosscheck':True,'instance':'Copy'}]}
  rows=[sample(0,1,9),sample(0,2,9),sample(0,3,2),sample(1,2,8),sample(1,3,4)]
  report=summarize(rows)
  self.assertEqual(report[0]['intervals'],1)
  self.assertEqual(report[0]['engine_work_ms'],2)
  self.assertEqual(report[1]['engine_work_ms'],4)
  self.assertIsNone(report[2]['engine_work_percent_of_wall'])
  rows.insert(3,sample(0,4,3))
  rows[2]['engines'][0]['unit_crosscheck']=False
  report=summarize(rows)
  self.assertEqual(report[0]['intervals'],0)
  self.assertEqual(report[0]['excluded_unverified_intervals'],2)

if __name__=='__main__':unittest.main()
