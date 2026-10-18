"""Compare generated tone spectra and MIDI envelopes, separately from API control values."""
import argparse,csv,json,wave
from pathlib import Path
import numpy as np
from test_runtime import sha,ORIGINAL_DLL

def edges(mask):
 changes=np.flatnonzero(np.diff(np.r_[False,mask,False]))
 return list(zip(changes[::2],changes[1::2]))

def spectrum(signal,rate):
 if len(signal)<rate//10:raise ValueError('Too little sustained signal for spectrum')
 size=1<<(len(signal)-1).bit_length()
 values=np.abs(np.fft.rfft(signal*np.hanning(len(signal)),n=size))
 low=max(1,int(100*size/rate));high=min(len(values),int(2500*size/rate))
 peak=int(np.argmax(values[low:high]))+low
 offset=0.0
 if 0<peak<len(values)-1:
  a,b,c=np.log(np.maximum(values[peak-1:peak+2],1e-20));denominator=a-2*b+c
  if denominator:offset=float(.5*(a-c)/denominator)
 return (peak+offset)*rate/size

def analyze(folder):
 acquired=json.loads((folder/'summary.json').read_text())
 if not acquired['passed'] or acquired['capture']['discontinuities'] or acquired['capture']['timestamp_errors']:raise ValueError('Acquisition has gaps or invalid timestamps')
 with wave.open(str(folder/'output.wav')) as stream:
  if (stream.getnchannels(),stream.getsampwidth(),stream.getframerate())!=(2,2,44100):raise ValueError('Unexpected capture format')
  rate=stream.getframerate();audio=np.frombuffer(stream.readframes(stream.getnframes()),'<i2').reshape(-1,2).mean(axis=1)/32768.
 block=rate//100;trimmed=audio[:len(audio)//block*block]
 rms=np.sqrt(np.mean(trimmed.reshape(-1,block)**2,axis=1))
 first=edges(rms>.001)
 if not first:raise ValueError('No process audio was captured')
 anchor=first[0][0]/100
 with (folder/'audio-stages.csv').open() as stream:stages=list(csv.DictReader(stream))
 formats=('ogg','mp3','wma') if acquired.get('scenario')=='Same-process compressed tone pitch changes' else ('wav','mid')
 expected=[(acquired['case']['format'],acquired['case']['pitch'])] if 'case' in acquired else [(f,p) for f in formats for p in (50,100,150)]
 if [(row['format'],int(row['pitch'])) for row in stages]!=expected:raise ValueError('Incomplete audio stages')
 if any(float(row['end'])-float(row['start'])>8 for row in stages):raise ValueError('Audio stage delayed by a foreground wait; rerun the case')
 began=float(stages[0]['start']);results=[]
 packet_epoch=acquired['capture'].get('first_packet_epoch_seconds')
 for row in stages:
  begin=float(row['start'])-packet_epoch if packet_epoch else anchor+float(row['start'])-began
  finish=float(row['end'])-packet_epoch if packet_epoch else anchor+float(row['end'])-began
  played=float(row['played'])-packet_epoch if packet_epoch and 'played' in row else None
  left=max(0,int((begin-.12)*100));right=min(len(rms),int((finish+.08)*100))
  section=rms[left:right];threshold=max(.001,float(np.quantile(section,.8))*.5)
  runs=[((a+left)/100,(b+left)/100) for a,b in edges(section>threshold) if b-a>=8]
  if not runs:raise ValueError('No sustained sound for '+str(row))
  # The final loop may be stopped by the fixture; use complete runs and onset intervals.
  complete=runs[:-1] if row['format']=='mid' else [(a,b) for a,b in runs if b<finish-.1]
  start=runs[0][0]+.15;end=min(runs[0][1]-.04,start+.35)
  frequency=spectrum(audio[int(start*rate):int(end*rate)],rate)
  intervals=np.diff([a for a,_ in runs]).tolist()
  results.append({'format':row['format'],'pitch':int(row['pitch']),'spectral_peak_hz':frequency,'half_amplitude_runs_seconds':runs,'complete_envelope_lengths_seconds':[b-a for a,b in complete],'onset_intervals_seconds':intervals,'threshold_rms':threshold,'first_onset_after_play_seconds':runs[0][0]-played if played is not None else None})
 return {'dll_sha256':acquired['dll_sha256'],'source_sha256':acquired['source_sha256'],'fixtures':acquired.get('fixtures'),'wave_sha256':sha(folder/'output.wav'),'seconds':len(audio)/rate,'phases':results}

def analyze_engine(folder):
 if (folder/'summary.json').exists():return analyze(folder)
 cases=[analyze(folder/(f+'-'+str(p))) for f in ('wav','mid') for p in (50,100,150)]
 if len({case['dll_sha256'] for case in cases})!=1:raise ValueError('Audio cases used different DLLs')
 if any((case['source_sha256'],case['fixtures'])!=(cases[0]['source_sha256'],cases[0]['fixtures']) for case in cases):raise ValueError('Audio cases used different harnesses or tones')
 return {'dll_sha256':cases[0]['dll_sha256'],'source_sha256':cases[0]['source_sha256'],'fixtures':cases[0]['fixtures'],'captures':cases,'phases':[phase for case in cases for phase in case['phases']]}

def check_phase(old,new):
 if (old['format'],old['pitch'])!=(new['format'],new['pitch']) or old['format'] not in ('wav','ogg','mp3','wma','mid'):raise ValueError('Mismatched or unsupported audio phase')
 result={'format':old['format'],'pitch':old['pitch'],'original_peak_hz':old['spectral_peak_hz'],'replacement_peak_hz':new['spectral_peak_hz'],'spectral_peak_difference_hz':new['spectral_peak_hz']-old['spectral_peak_hz'],'peak_matches_within_2hz':abs(new['spectral_peak_hz']-old['spectral_peak_hz'])<2}
 if old['format']!='mid':
  expected=440 if old['format']=='wma' else 440*old['pitch']/100
  result['generated_tone_valid']=abs(old['spectral_peak_hz']-expected)<2 and abs(new['spectral_peak_hz']-expected)<2
  result['coverage_valid']=bool(old['complete_envelope_lengths_seconds'] and new['complete_envelope_lengths_seconds'])
  if old['format']=='wav':result['envelope_matches_within_50ms']=result['coverage_valid'] and all(round(abs(value-100/old['pitch']),9)<=.05 for phase in (old,new) for value in phase['complete_envelope_lengths_seconds'])
  else:
   # Codec padding belongs to the original decoder oracle; do not assume a lossy file is exactly one second.
   result['original_envelope_reference_seconds']=float(np.median(old['complete_envelope_lengths_seconds'])) if result['coverage_valid'] else None
   result['envelope_matches_within_50ms']=result['coverage_valid'] and all(round(abs(value-result['original_envelope_reference_seconds']),9)<=.05 for value in new['complete_envelope_lengths_seconds'])
  result['passed']=result['generated_tone_valid'] and result['peak_matches_within_2hz'] and result['envelope_matches_within_50ms']
 else:
  for label,phase in [('original',old),('replacement',new)]:
   result[label+'_median_loop_seconds']=float(np.median(phase['onset_intervals_seconds'])) if phase['onset_intervals_seconds'] else None
   result[label+'_median_envelope_seconds']=float(np.median(phase['complete_envelope_lengths_seconds'])) if phase['complete_envelope_lengths_seconds'] else None
  result['coverage_valid']=all(len(phase[key])>=3 for phase in (old,new) for key in ('onset_intervals_seconds','complete_envelope_lengths_seconds'))
  result['loop_matches_within_50ms']=result['coverage_valid'] and all(round(abs(value-result['original_median_loop_seconds']),9)<=.05 for value in new['onset_intervals_seconds'])
  result['envelope_matches_within_50ms']=result['coverage_valid'] and all(round(abs(value-result['original_median_envelope_seconds']),9)<=.05 for value in new['complete_envelope_lengths_seconds'])
  result['passed']=result['peak_matches_within_2hz'] and result['loop_matches_within_50ms'] and result['envelope_matches_within_50ms']
  if old.get('first_onset_after_play_seconds') is not None and new.get('first_onset_after_play_seconds') is not None:
   result['first_note_start_difference_seconds']=new['first_onset_after_play_seconds']-old['first_onset_after_play_seconds']
   result['first_note_not_delayed_over_100ms']=bool(new['first_onset_after_play_seconds']>=-.05 and result['first_note_start_difference_seconds']<=.1)
   result['passed'] = result['passed'] and result['first_note_not_delayed_over_100ms']
 return result

def compare(folder):
 original=analyze_engine(folder/'original');replacement=analyze_engine(folder/'replacement')
 if original['dll_sha256']!=ORIGINAL_DLL or replacement['dll_sha256']==ORIGINAL_DLL:raise ValueError('Comparison does not identify original and independent replacement DLLs')
 if (original['source_sha256'],original['fixtures'])!=(replacement['source_sha256'],replacement['fixtures']):raise ValueError('Comparison used different harnesses or generated tones')
 checks=[check_phase(old,new) for old,new in zip(original['phases'],replacement['phases'])]
 return {'measurement_valid':all(row['coverage_valid'] for row in checks),'tone_and_envelope_gate_passed':all(row['passed'] for row in checks),'analysis_source_sha256':sha(Path(__file__)),'scope':'One process-specific PCM pair; dominant spectrum within 2Hz; each complete 10ms RMS half-amplitude envelope and loop interval within 50ms of reference. At least three complete MIDI notes/intervals required. Timed captures require first-note onset after the play call no more than 100ms later than reference; earlier response is allowed and reported, not called timing identity. Final MIDI run omitted because the fixture stops mid-loop. Not full waveform identity, physical speaker latency, all instruments, volumes, ME resume or general audio certification.','original':original,'replacement':replacement,'checks':checks}

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('folder',type=Path);a=ap.parse_args()
 result=compare(a.folder.resolve());output=a.folder/'comparison.json'
 if output.exists():raise FileExistsError(output)
 output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['checks'],indent=2))
 if not result['tone_and_envelope_gate_passed']:raise RuntimeError('Tone/envelope comparison failed; see '+str(output))

if __name__=='__main__':main()
