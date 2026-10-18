"""Compare actual WMA pitch in four roles; do not infer loop or restart policy from one sine."""
import argparse,csv,json,wave
from pathlib import Path
import numpy as np
from analyze_runtime_waveform import spectrum
from test_runtime import sha,ORIGINAL_DLL

def features(folder):
 report=json.loads((folder/'summary.json').read_text());capture=report['capture']
 assert report['passed'] and report['case']=={'format':'wma-roles','pitch':100}
 assert capture['target_exited'] and not capture['discontinuities'] and not capture['timestamp_errors']
 with wave.open(str(folder/'output.wav')) as source:
  assert (source.getnchannels(),source.getsampwidth(),source.getframerate())==(2,2,44100)
  rate=source.getframerate();audio=np.frombuffer(source.readframes(source.getnframes()),'<i2').reshape(-1,2).mean(axis=1)/32768.
 rows=list(csv.DictReader((folder/'wma-roles.csv').open()))
 assert [(row['role'],int(row['pitch'])) for row in rows]==[(role,pitch) for role in ('bgm','bgs','me','se') for pitch in (50,100,150)]
 results=[]
 for row in rows:
  assert .7<float(row['end'])-float(row['played'])<1.85,'Foreground delay or incomplete WMA stage'
  begin=float(row['played'])-capture['first_packet_epoch_seconds']+.3
  left=int(begin*rate);right=int((begin+.4)*rate);assert 0<=left<right<=len(audio)
  clip=audio[left:right];assert np.sqrt(np.mean(clip**2))>.001,'Silent WMA stage'
  results.append({'role':row['role'],'pitch':int(row['pitch']),'peak_hz':spectrum(clip,rate)})
 return {'dll_sha256':report['dll_sha256'],'source_sha256':report['source_sha256'],'fixtures':report['fixtures'],'wave_sha256':sha(folder/'output.wav'),'checks':results}

def compare(folder):
 old=features(folder/'original');new=features(folder/'replacement')
 assert old['dll_sha256']==ORIGINAL_DLL and new['dll_sha256']!=ORIGINAL_DLL
 assert (old['source_sha256'],old['fixtures'])==(new['source_sha256'],new['fixtures'])
 checks=[]
 for a,b in zip(old['checks'],new['checks']):
  assert (a['role'],a['pitch'])==(b['role'],b['pitch'])
  passed=abs(a['peak_hz']-440)<2 and abs(b['peak_hz']-440)<2 and abs(a['peak_hz']-b['peak_hz'])<2
  checks.append({'role':a['role'],'pitch':a['pitch'],'original_peak_hz':a['peak_hz'],'replacement_peak_hz':b['peak_hz'],'passed':passed})
 return {'passed':all(row['passed'] for row in checks),'dll_sha256':new['dll_sha256'],'original':old,'replacement':new,'checks':checks,'analysis_sha256':sha(Path(__file__)),'scope':'One generated WMAv2 440Hz tone; BGM/BGS/ME/SE at requested pitch 50/100/150; process PCM 0.3..0.7 seconds after play return. Original WMA ignores pitch. Not same-file restart, loop boundary, all WMA codec variants or physical speaker latency certification.'}

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('folder',type=Path);a=ap.parse_args()
 result=compare(a.folder);output=a.folder/'wma-roles-comparison.json'
 if output.exists():raise FileExistsError(output)
 output.write_text(json.dumps(result,indent=2))
 assert result['passed'],result['checks']
 print('Original/replacement WMAv2 pitch in twelve role/pitch cases: PASS')

if __name__=='__main__':main()
