import io,json,sys,tempfile,unittest,zipfile,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import runtime_validation as v
from verify_runtime import Validator
from benchmark_runtime_browser import full_cases
import reuse_ci

class ValidationPolicyTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir=v.ROOT/'build');self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.runtime=self.root/'runtime';self.runtime.mkdir()
  (self.root/'src/runtime').mkdir(parents=True);(self.root/'src/runtime/sample.cpp').write_text('one')
  for name in list(v.DLLS.values())+['rgssxp-ruby.exe','display_geometry_test.exe','direction_input_test.exe','text_submit_test.exe']:(self.runtime/name).write_bytes(b'owned test binary')
 def test_build_stamp_refuses_source_and_binary_changes(self):
  v.stamp(self.runtime,self.root);v.check_build(self.runtime,self.root)
  (self.root/'src/runtime/sample.cpp').write_text('two')
  with self.assertRaisesRegex(ValueError,'rebuild'):v.check_build(self.runtime,self.root)
  v.stamp(self.runtime,self.root);(self.runtime/'Lunetile.dll').write_bytes(b'other')
  with self.assertRaisesRegex(ValueError,'rebuild'):v.check_build(self.runtime,self.root)
 def test_missing_stamp_requires_build(self):
  with self.assertRaisesRegex(ValueError,'stamp missing'):v.check_build(self.runtime,self.root)
 def test_engine_selection_and_unknown_fallback(self):
  self.assertEqual(v.selection(['src/runtime/vxa.rb'])['engines'],['vxa'])
  self.assertEqual(v.selection(['src/runtime/xp_tile_cache.cpp'])['engines'],['xp'])
  self.assertEqual(v.selection(['src/runtime/renderer.cpp'])['engines'],['vxa','xp'])
  self.assertEqual(v.selection(['new/unknown.file'])['engines'],['vxa','xp'])
  self.assertEqual(v.selection(['docs/BROWSER.md'])['engines'],[])
 def test_cache_checks_every_identity_dimension_and_evidence(self):
  cache=v.Receipts(self.root/'cache');folder=self.root/'case';folder.mkdir();proof=folder/'proof.json';proof.write_text('ok')
  context={n:n for n in ['dll','test','helper','launcher','data','config','environment']}
  cache.store('xp.types',context,'passed',folder);self.assertIsNotNone(cache.load('xp.types',context))
  for key in context:self.assertIsNone(cache.load('xp.types',dict(context,**{key:'changed'})))
  proof.write_text('corrupt');self.assertIsNone(cache.load('xp.types',context))
  proof.unlink();self.assertIsNone(cache.load('xp.types',context))
 def test_failure_invalidates_older_success(self):
  cache=v.Receipts(self.root/'cache');folder=self.root/'case';folder.mkdir();(folder/'proof').write_text('ok')
  cache.store('test',{},'passed',folder);cache.store('test',{},'failed',folder)
  self.assertIsNone(cache.load('test',{}))
 def test_project_copy_location_does_not_break_content_identity(self):
  for name in ['a','b']:
   data=self.root/name/'xp/Data';data.mkdir(parents=True);(data/'Map001.rxdata').write_bytes(b'same fixture')
  with patch('runtime_validation.environment',return_value={}):
   self.assertEqual(v.identity(self.runtime,self.root/'a',self.root),v.identity(self.runtime,self.root/'b',self.root))
 def test_environment_and_identity_survive_json_round_trip(self):
  context=v.identity(self.runtime,self.root,self.root)
  self.assertEqual(context,json.loads(json.dumps(context)))
 def test_live_case_ignores_successful_receipt(self):
  out=self.root/'out';out.mkdir();evidence=self.root/'evidence';evidence.mkdir();(evidence/'pass').write_text('ok')
  with patch('verify_runtime.policy.identity',return_value={}):runner=Validator(out,'release',self.runtime,self.root,dict(engines=[],groups=[]),self.root/'cache')
  runner.cache.store('xp.lifecycle',{},'passed',evidence);calls=[]
  runner.case('xp.lifecycle',lambda f:calls.append(1));self.assertEqual(calls,[1]);self.assertEqual(runner.report['checks'][0]['status'],'passed')
 def test_prepackage_proof_is_not_a_completed_release(self):
  report=dict(validation_schema=1,mode='release',formal=False,passed=True,phase='prepackage',selection=dict(engines=[],groups=[]),artifacts={},checks=[dict(id='python',status='passed')],identity={'fixture':'same'},projects_directory=str(self.root))
  with patch('runtime_validation.identity',return_value={'fixture':'same'}):self.assertTrue(v.require_report(report,self.runtime,purpose='package'))
  with patch('runtime_validation.identity',return_value={'fixture':'changed'}):
   with self.assertRaisesRegex(ValueError,'environment changed'):v.require_report(report,self.runtime,purpose='package')
  with self.assertRaises(ValueError):v.require_report(report,self.runtime)
 def test_missing_skipped_and_duplicate_required_cases_fail(self):
  for records in [[],[dict(id='a',status='skipped')],[dict(id='a',status='failed')],[dict(id='a',status='passed')]*2]:
   with self.assertRaises(ValueError):v.require_cases(dict(required=['a'],checks=records))
  self.assertTrue(v.require_cases(dict(required=['a'],checks=[dict(id='a',status='reused')])))
 def test_declared_required_list_cannot_hide_missing_mode_requirements(self):
  report=dict(mode='release',selection=dict(engines=['xp'],groups=[]),required=[],checks=[])
  with self.assertRaises(ValueError):v.require_cases(report,v.expected_cases(report))
  self.assertIn('xp.save-restart',v.expected_cases(report));self.assertIn('xp.lifecycle',v.expected_cases(report))
  self.assertIn('package.extraction',v.expected_cases(report))
 def test_formal_schedule_is_unchanged_and_quick_budget_is_52_seconds(self):
  cases=full_cases();self.assertEqual(len(cases)*2,44);self.assertEqual(sum(c[-1] for c in cases)*2,1000)
  self.assertEqual(2*(2*2*5+2*3),52)
 def test_formal_and_release_require_fresh_live_cases(self):
  report=dict(mode='performance',selection=dict(engines=['xp','vxa'],groups=['browser']))
  ids=v.expected_cases(report)
  self.assertIn('output.formal',ids);self.assertIn('package.extraction',ids)
  self.assertNotIn('package.extraction',v.expected_cases(report,prepackage=True))
 def test_first_failure_retained_and_no_automatic_retry(self):
  out=self.root/'out';out.mkdir()
  with patch('verify_runtime.policy.identity',return_value={}):runner=Validator(out,'quick',self.runtime,self.root,dict(engines=[],groups=[]),self.root/'cache')
  calls=[]
  def failure(folder):calls.append(1);raise RuntimeError('first failure')
  with self.assertRaisesRegex(RuntimeError,'first failure'):runner.case('test',failure)
  result=json.loads((out/'verification.json').read_text());self.assertFalse(result['passed']);self.assertIn('first failure',result['checks'][0]['reason']);self.assertEqual(calls,[1])
  with self.assertRaisesRegex(ValueError,'Duplicate'):runner.case('test',failure)
 def test_report_cannot_use_running_or_changed_runtime(self):
  report=dict(validation_schema=1,passed=True,phase='running')
  with self.assertRaises(ValueError):v.require_report(report,self.runtime)
 def test_legacy_four_path_cli_is_preserved(self):
  import verify_runtime
  with patch('sys.argv',['verify_runtime.py','project','original.dll','save','out']),patch('verify_runtime_legacy.main') as old:
   verify_runtime.main();old.assert_called_once()
 def test_diagnostic_cannot_certify_release(self):
  report=dict(validation_schema=1,mode='quick',formal=False,passed=True,phase='diagnostic')
  with self.assertRaisesRegex(ValueError,'not completed'):v.require_report(report,self.runtime)
 def test_quick_cannot_be_labelled_formal(self):
  report=dict(validation_schema=1,mode='quick',formal=True,passed=True,phase='complete')
  with self.assertRaisesRegex(ValueError,'formal claim'):v.require_report(report,self.runtime)
 def test_module_monitor_hashes_once_instead_of_each_poll_and_keeps_integrity_guard(self):
  import test_runtime as harness
  from types import SimpleNamespace
  source=self.root/'source.dll';source.write_bytes(b'owned DLL');exe=self.root/'Game.exe';exe.write_bytes(b'owned launcher')
  for repeats in [2,100]:
   output=self.root/str(repeats);polls=[]
   def poll():polls.append(1);return None if len(polls)<=repeats else 0
   def start(*args,**kwargs):
    (output/'rgssxp.log').write_text('Ruby finalized');(output/'runtime-complete.txt').write_text('done,false,false')
    return SimpleNamespace(pid=9876,poll=poll,returncode=0)
   harness.MODULE_HASHES.clear()
   maps=SimpleNamespace(memory_maps=lambda:[SimpleNamespace(path=str(output/'Lunetile.dll'))])
   with patch.object(harness.subprocess,'Popen',side_effect=start),patch.object(harness.psutil,'Process',return_value=maps),patch.object(harness.time,'sleep'),patch.object(harness,'sha',wraps=harness.sha) as hashing:
    result=harness.run(exe,source,output,'',b'fixture')
    self.assertEqual(hashing.call_count,3)
    self.assertEqual(result['runtime_sha256'],harness.sha(source))

class CIReuseTests(unittest.TestCase):
 def archive(self,sha='commit',corrupt=False):
  inner=io.BytesIO()
  with zipfile.ZipFile(inner,'w') as z:z.writestr('owned.txt','fixture')
  names={'lunetile-template-'+e+'-'+s+'.zip' for e in ['xp','vxa'] for s in ['windows-x86','diagnostics']}
  names.update(['lunetile-vxa-editor-fix.zip','lunetile-vxa-speed-fix.zip','lunetile-xp-speed-fix.zip'])
  sums={n:hashlib.sha256(inner.getvalue()).hexdigest() for n in names}
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as z:
   for n in names:z.writestr(n,inner.getvalue())
   z.writestr('SHA256SUMS.txt',''.join(h+'  '+n+'\n' for n,h in sums.items()))
   z.writestr('ci-provenance.json',json.dumps(dict(schema=1,passed=not corrupt,source_commit=sha,workflow=reuse_ci.WORKFLOW,assets=sums)))
  return out.getvalue()
 def run_data(self):return dict(id=7,head_sha='commit',head_branch='main',event='push',path=reuse_ci.WORKFLOW,status='completed',conclusion='success',head_repository=dict(full_name='owner/repo'),html_url='https://github.com/owner/repo/actions/runs/7')
 def test_matching_main_and_complete_artifacts_reuse(self):
  def request(route,raw=False):
   if raw:return self.archive()
   if '/artifacts?' in route:return dict(artifacts=[dict(name=n,id=i,expired=False) for i,n in enumerate(reuse_ci.REQUIRED)])
   return dict(workflow_runs=[self.run_data()])
  self.assertTrue(reuse_ci.find_reuse(request,'commit','owner/repo')['reuse'])
 def test_sha_fork_failure_expired_or_missing_artifact_build_normally(self):
  for field,value in [('head_sha','other'),('conclusion','failure'),('status','in_progress'),('head_branch','tag'),('event','pull_request'),('head_repository',dict(full_name='fork/repo'))]:
   self.assertFalse(reuse_ci.verified_run(dict(self.run_data(),**{field:value}),'commit','owner/repo'))
  for artifacts in [[],[dict(name=n,id=i,expired=True) for i,n in enumerate(reuse_ci.REQUIRED)]]:
   def request(route,raw=False):return dict(artifacts=artifacts) if '/artifacts?' in route else dict(workflow_runs=[self.run_data()])
   self.assertFalse(reuse_ci.find_reuse(request,'commit','owner/repo')['reuse'])
 def test_wrong_provenance_or_checksum_rejected(self):
  for data in [self.archive('wrong'),self.archive(corrupt=True)]:
   with self.assertRaises(ValueError):reuse_ci.verify_archive(data,'commit')
 def test_main_never_requests_reuse(self):
  with patch('reuse_ci.urllib.request.build_opener',side_effect=AssertionError('network')):
   self.assertFalse(reuse_ci.probe('commit','owner/repo','refs/heads/main','token')['reuse'])
