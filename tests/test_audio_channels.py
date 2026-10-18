import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_runtime_channels import channel_checks

class ChannelChecks(unittest.TestCase):
 def reference(self,held=False):
  power={key:{'bgm':0.,'bgs':0.,'me':0.,'rms':0.} for key in ('bgm','mix','me','me_solo','resumed','future_bgm','bgs_stopped','all_stopped','late_stopped')}
  power['bgm'].update(bgm=1.,rms=.04)
  power['mix']['bgs']=power['me']['bgs']=power['resumed']['bgs']=1.
  power['me']['me']=power['me_solo']['me']=1.
  power['future_bgm']['bgm']=power['bgs_stopped']['bgm']=0. if held else 1.
  power['all_stopped']['rms']=.0018
  power['late_stopped']['rms']=.00002
  return power
 def test_note_gap_and_early_reverb_are_not_failures(self):
  power=self.reference()
  self.assertTrue(all(channel_checks(power,10**(-1750/2000),False).values()))
 def test_rejects_retriggered_held_note_missing_future_notes_and_stuck_tail(self):
  held=self.reference(True);held['future_bgm']['bgm']=1.
  self.assertFalse(channel_checks(held,.13,True)['bgm_after_me_matches_source'])
  silent=self.reference();silent['future_bgm']['bgm']=0.
  self.assertFalse(channel_checks(silent,.13,False)['bgm_after_me_matches_source'])
  stuck=copy.deepcopy(silent);stuck['late_stopped']['rms']=.04
  self.assertFalse(channel_checks(stuck,.13,False)['all_channels_stopped'])

if __name__=='__main__':unittest.main()
