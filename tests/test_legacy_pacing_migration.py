import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from migrate_project import ROOT,sha,strip_legacy_pacing

class LegacyPacingTests(unittest.TestCase):
 def setUp(self):
  self.legacy=json.loads((ROOT/'src/runtime/legacy_pacing.json').read_text())
  self.stock='begin\r\n  game\r\nrescue\r\n  raise\r\nend\r\n'
  self.wrapped=self.stock.replace('\r\n','\n').replace('begin\n','begin\n'+self.legacy['start_line'])
  index=self.wrapped.rfind('end\n')
  self.wrapped=self.wrapped[:index]+self.legacy['detach_block']+self.wrapped[index:]
 def test_known_bootstraps_match_reviewed_hashes(self):
  self.assertEqual([sha(body.encode()) for body in self.legacy['bootstrap_sources']], [
   '221127177ead0b10bd18bf65acfdb77ed6fd882ad0b857c0afdd3ab6ee808cec',
   '2d8edbba3f4c40553f19a9bc7ef89d9ed84530267520aaed76c51b7e385ae99e'])
 def test_inline_and_separate_hooks_restore_reviewed_main_only(self):
  digest=sha(self.stock.encode())
  for body in self.legacy['bootstrap_sources']:
   for text in [body+self.wrapped,(body+self.wrapped).replace('\n','\r\n')]:
    self.assertEqual(strip_legacy_pacing(text,digest,self.legacy),self.stock.replace('\r\n','\n'))
  self.assertEqual(strip_legacy_pacing(self.wrapped,digest,self.legacy,True),self.stock.replace('\r\n','\n'))
 def test_unknown_main_missing_bootstrap_or_modified_hook_is_rejected(self):
  body=self.legacy['bootstrap_sources'][0];digest=sha(self.stock.encode())
  for text,separate in [(self.wrapped,False),(body+self.wrapped+'puts :custom\n',False),(body.replace('Attach','OtherAttach')+self.wrapped,False),(body+self.wrapped.replace('::Detach.call','::Detach.call(1)'),False),(body+self.wrapped,True)]:
   self.assertIsNone(strip_legacy_pacing(text,digest,self.legacy,separate))

if __name__=='__main__':unittest.main()
