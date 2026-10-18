"""Check actual channel PCM presence, volume law and MIDI ME resume; not full audio certification."""
import argparse,csv,json,math,wave
from pathlib import Path
import numpy as np
from test_runtime import sha,ORIGINAL_DLL
from analyze_runtime_waveform import spectrum

def band(signal,rate,frequency):
 if len(signal)<rate//10:raise ValueError('Channel analysis needs at least 100ms')
 window=np.hanning(len(signal));bins=np.fft.rfftfreq(len(signal),1/rate)
 values=np.abs(np.fft.rfft(signal*window))**2
 return float(values[np.abs(bins-frequency)<=15].sum()/(len(signal)*np.sum(window**2)))

def band_level(signal,rate,frequency):
 width=rate//10
 values=[band(signal[i:i+width],rate,frequency) for i in range(0,len(signal)-width+1,width)]
 if not values:raise ValueError('No complete channel analysis window')
 return float(np.quantile(values,.8))

def channel_checks(power,gain,held):
 baseline=power['bgm']['bgm'];bgs=power['mix']['bgs'];effect=power['me_solo']['me']
 return {'volume50_gain':abs(gain-10**(-1750/2000))<=.02,
         'bgm_paused_during_me':power['me']['bgm']<baseline*.1,
         'me_actually_sounded':power['me']['me']>effect*.3,
         'bgs_survived_me':.5<power['me']['bgs']/bgs<2,
         'bgm_after_me_matches_source':power['future_bgm']['bgm']<baseline*.1 if held else .1<power['future_bgm']['bgm']/baseline<2,
         'bgs_survived_me_teardown':.5<power['resumed']['bgs']/bgs<2,
         'bgm_after_bgs_stop_matches_source':power['bgs_stopped']['bgm']<baseline*.1 if held else .1<power['bgs_stopped']['bgm']/baseline<2,
         'bgs_really_stopped':power['bgs_stopped']['bgs']<bgs*.05,
         'all_channels_stopped':power['late_stopped']['rms']<max(.001,power['bgm']['rms']*.05)}

def features(folder):
 report=json.loads((folder/'summary.json').read_text());capture=report['capture']
 assert report['passed'] and report['case']['format'] in ('channels','channels-held','channels-repeat') and report['case']['pitch']==100
 held=report['case']['format']!='channels-repeat'
 assert not capture['discontinuities'] and not capture['timestamp_errors'] and capture['target_exited']
 with wave.open(str(folder/'output.wav')) as source:
  assert (source.getnchannels(),source.getsampwidth(),source.getframerate())==(2,2,44100)
  rate=source.getframerate();audio=np.frombuffer(source.readframes(source.getnframes()),'<i2').reshape(-1,2).mean(axis=1)/32768.
 rows=list(csv.DictReader((folder/'audio-channel-stages.csv').open()))
 expected=['bgm','volume50','mix','me','resumed','bgs_stopped','all_stopped','me_solo']
 assert [row['stage'] for row in rows]==expected
 clips={};stages={row['stage']:row for row in rows}
 def clip(begin,end):
  left=int((begin-capture['first_packet_epoch_seconds'])*rate);right=int((end-capture['first_packet_epoch_seconds'])*rate)
  assert 0<=left<right<=len(audio)
  return audio[left:right]
 for row in rows:
  name=row['stage'];played=float(row['played'])
  assert float(row['end'])-played<=int(row['frames'])/40+.25,'Foreground wait invalidated the channel capture'
  begin,end=(.35,.55) if name in ('me','me_solo') else (.3,.7) if name=='all_stopped' else (.5,1.3)
  assert played+end<=float(row['end'])
  clips[name]=clip(played+begin,played+end)
 stop=float(stages['all_stopped']['played'])
 assert stop+2.1<=float(stages['all_stopped']['end']),'Need a longer stop stage to distinguish reverb decay from stuck audio'
 clips['late_stopped']=clip(stop+1.5,stop+2.1)
 clips['future_bgm']=clip(float(stages['resumed']['played'])+.5,float(stages['bgs_stopped']['end']))
 bgm=spectrum(clips['bgm'],rate);me=spectrum(clips['me_solo'],rate)
 power={name:{'bgm':band_level(clip,rate,bgm),'bgs':band_level(clip,rate,700),'me':band_level(clip,rate,me),'rms':float(np.sqrt(np.mean(clip**2)))} for name,clip in clips.items()}
 baseline=power['bgm']['bgm'];bgs=power['mix']['bgs'];effect=power['me_solo']['me']
 assert min(baseline,bgs,effect)>1e-7,'No usable channel calibration signal'
 gain=math.sqrt(power['volume50']['bgm']/baseline)
 checks=channel_checks(power,gain,held)
 return {'dll_sha256':report['dll_sha256'],'source_sha256':report['source_sha256'],'fixtures':report['fixtures'],'wave_sha256':sha(folder/'output.wav'),'bgm_pattern':'held' if held else 'repeat','bgm_peak_hz':bgm,'me_peak_hz':me,'volume50_gain':gain,'power':power,'checks':checks,'passed':all(checks.values())}

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('folder',type=Path);a=ap.parse_args();out=a.folder/'channels-comparison.json'
 if out.exists():raise FileExistsError(out)
 cases=[]
 patterns=('held',) if (a.folder/'original/summary.json').exists() else ('held','repeat')
 for pattern in patterns:
  old=features(a.folder/'original'/(pattern if len(patterns)>1 else ''));new=features(a.folder/'replacement'/(pattern if len(patterns)>1 else ''))
  assert old['dll_sha256']==ORIGINAL_DLL!=new['dll_sha256']
  assert (old['source_sha256'],old['fixtures'])==(new['source_sha256'],new['fixtures'])
  level=10*math.log10(new['power']['bgm']['bgm']/old['power']['bgm']['bgm'])
  rms=20*math.log10(new['power']['bgm']['rms']/old['power']['bgm']['rms'])
  pitch=abs(new['bgm_peak_hz']-old['bgm_peak_hz'])<2 and abs(new['me_peak_hz']-old['me_peak_hz'])<2
  cases.append({'pattern':pattern,'passed':old['passed'] and new['passed'] and pitch,'generated_pitch_matches':pitch,'absolute_bgm_band_level_difference_db':level,'absolute_bgm_rms_level_difference_db':rms,'original':old,'replacement':new})
 assert len({case['replacement']['dll_sha256'] for case in cases})==1
 report={'passed':all(case['passed'] for case in cases),'scope':'Process-specific generated held/repeated MIDI BGM, MIDI ME and 700Hz WAV BGS; actual PCM volume, pause/resume presence and channel teardown. Uses 80th-percentile 100ms band power. Interrupted held notes must stay silent; future repeated notes must sound across the post-ME observation, without assuming full volume in an early silent note gap. Stop silence is checked at 1.5-2.1 seconds; early 0.3-0.7s reverb RMS is retained separately. Absolute band and total-RMS differences are descriptive. This functional gate does not certify resume phase, transient/reverb waveform identity, all instruments or speaker latency.','analysis_source_sha256':sha(Path(__file__)),'cases':cases}
 out.write_text(json.dumps(report,indent=2));print(json.dumps({'passed':report['passed'],'cases':[{k:case[k] for k in ('pattern','passed','absolute_bgm_band_level_difference_db','absolute_bgm_rms_level_difference_db')} for case in cases]},indent=2))
 if not report['passed']:raise RuntimeError('Channel comparison failed; see '+str(out))

if __name__=='__main__':main()
