"""Compare generated held-note MIDI gain in actual original/replacement process PCM."""
import argparse,csv,json,math,wave
from pathlib import Path
import numpy as np
from test_runtime import sha,ORIGINAL_DLL
from analyze_runtime_channels import band_level
from analyze_runtime_waveform import spectrum

def matching_gain(reference,gain):
 return abs(gain-reference)<=max(.002,reference*.12)

def features(folder):
 report=json.loads((folder/'summary.json').read_text());capture=report['capture']
 assert report['passed'] and report['case']=={'format':'volumes','pitch':100}
 assert capture['target_exited'] and not capture['discontinuities'] and not capture['timestamp_errors']
 with wave.open(str(folder/'output.wav')) as source:
  assert (source.getnchannels(),source.getsampwidth(),source.getframerate())==(2,2,44100)
  rate=source.getframerate();audio=np.frombuffer(source.readframes(source.getnframes()),'<i2').reshape(-1,2).mean(axis=1)/32768.
 rows=list(csv.DictReader((folder/'audio-volume-stages.csv').open()))
 assert [int(row['volume']) for row in rows]==[100,0,1,25,50,75,100]
 clips=[]
 for row in rows:
  played=float(row['played'])
  assert float(row['end'])-played<=int(row['frames'])/40+.25,'Foreground wait invalidated capture'
  left=int((played+1.1-capture['first_packet_epoch_seconds'])*rate);right=int((played+1.45-capture['first_packet_epoch_seconds'])*rate)
  assert 0<=left<right<=len(audio) and played+1.45<=float(row['end'])
  clips.append(audio[left:right])
 frequency=spectrum(clips[0],rate);baseline=band_level(clips[0],rate,frequency)
 assert baseline>1e-7,'No usable held-note calibration signal'
 steps=[]
 for row,clip in zip(rows,clips):
  volume=int(row['volume']);gain=math.sqrt(band_level(clip,rate,frequency)/baseline)
  steps.append({'volume':volume,'measured_gain':gain,'ideal_db_curve_gain':0 if volume==0 else 10**((volume-100)*35/2000)})
 gains=[step['measured_gain'] for step in steps]
 assert gains[1]<.002 and all(a<b for a,b in zip(gains[1:],gains[2:])) and .98<gains[-1]<1.02,'Invalid silent/monotonic/stable-full-scale calibration'
 return {'steps':steps,'peak_hz':frequency,'reference_band_power':baseline,'dll_sha256':report['dll_sha256'],'source_sha256':report['source_sha256'],'fixtures':report['fixtures'],'wave_sha256':sha(folder/'output.wav')}

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('folder',type=Path);ap.add_argument('--output',default='volumes-comparison.json');a=ap.parse_args();out=a.folder/a.output
 if out.exists():raise FileExistsError(out)
 old=features(a.folder/'original');new=features(a.folder/'replacement')
 assert old['dll_sha256']==ORIGINAL_DLL!=new['dll_sha256']
 assert (old['source_sha256'],old['fixtures'])==(new['source_sha256'],new['fixtures'])
 checks=[{'volume':o['volume'],'passed':matching_gain(o['measured_gain'],n['measured_gain'])} for o,n in zip(old['steps'],new['steps'])]
 report={'passed':all(check['passed'] for check in checks),'checks':checks,'original':old,'replacement':new,'analysis_source_sha256':sha(Path(__file__)),'absolute_bgm_band_difference_db':10*math.log10(new['reference_band_power']/old['reference_band_power']),'scope':'Six MIDI AudioPath gains compared with actual original PCM, generated held organ note, 1.1-1.45s settled windows after original reverb decays. Tolerance max(0.002 absolute,12 percent relative) against measured reference, not an assumed linear synth transfer function. Ideal dB gains are descriptive only. Not transient/envelope, absolute level or all-instrument certification.'}
 out.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
 if not report['passed']:raise RuntimeError('Physical MIDI volume comparison failed; see '+str(out))

if __name__=='__main__':main()
