import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from review_runtime_gpu_memory import review


class GpuMemoryReviewTests(unittest.TestCase):
 def setUp(self):
  root=Path(__file__).resolve().parents[1]/'build/test-runtime-gpu-memory';root.mkdir(parents=True,exist_ok=True)
  self.temporary=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temporary.cleanup)
  self.folder=Path(self.temporary.name)
  (self.folder/'Lunetile.dll').write_bytes(b'analysis unit fixture')
  self.digest=hashlib.sha256(b'analysis unit fixture').hexdigest()
  (self.folder/'boot-result.json').write_text(json.dumps({'passed':True,'dll_sha256':self.digest,'endurance':{'meets_duration_and_roundtrip_gate':True}}))
  (self.folder/'modules.json').write_text(json.dumps({'owned.dll':self.digest}))
  (self.folder/'gpu-memory-identity.json').write_text(json.dumps({'pid':42,'creation_ticks':123,'exe':str(self.folder/'Game.exe')}),encoding='utf-8-sig')
  self.rows=[{'pid':42,'creation_ticks':123,'active_seconds':i*30,'available':True,'rows':[{'Name':'pid_42_adapter0','DedicatedUsage':1000+i*30,'SharedUsage':100,'TotalCommitted':2000+i*30}]} for i in range(61)]

 def run_review(self):
  (self.folder/'gpu-memory-snapshots.jsonl').write_text('\n'.join(json.dumps(row) for row in self.rows),encoding='utf-8-sig')
  return review(self.folder)

 def test_completed_capture_has_correct_units_and_no_fabricated_zero(self):
  self.rows[1]['available']=False
  result=self.run_review()
  self.assertEqual(result['samples'],60)
  self.assertEqual(result['unavailable_samples'],1)
  metric=result['metrics']['DedicatedUsage']
  self.assertEqual(metric['minimum_bytes'],1000)
  self.assertAlmostEqual(metric['steady_slope_mib_per_minute'],60/1048576)

 def test_identity_change_is_rejected(self):
  self.rows[10]['creation_ticks']=124
  with self.assertRaises(AssertionError):self.run_review()

 def test_wrong_adapter_pid_is_rejected(self):
  self.rows[10]['rows'][0]['Name']='pid_420_adapter0'
  with self.assertRaises(AssertionError):self.run_review()

 def test_gap_and_incomplete_coverage_are_rejected(self):
  original=copy.deepcopy(self.rows)
  self.rows=self.rows[:5]+self.rows[8:]
  with self.assertRaises(AssertionError):self.run_review()
  self.rows=original[:55]
  with self.assertRaises(AssertionError):self.run_review()

 def test_invalid_counter_and_changed_dll_are_rejected(self):
  self.rows[10]['rows'][0]['DedicatedUsage']=-1
  with self.assertRaises(AssertionError):self.run_review()
  self.rows[10]['rows'][0]['DedicatedUsage']=1000
  (self.folder/'Lunetile.dll').write_bytes(b'changed')
  with self.assertRaises(AssertionError):self.run_review()


if __name__=='__main__':unittest.main()
