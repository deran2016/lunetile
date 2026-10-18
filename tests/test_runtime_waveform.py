import json,sys,tempfile,unittest,wave
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_runtime_waveform import analyze,edges,spectrum,check_phase
from analyze_runtime_channels import band,band_level

class WaveformTest(unittest.TestCase):
 def test_separated_channel_power_and_volume(self):
  rate=44100;t=np.arange(rate)/rate;sine=np.sin(2*np.pi*440*t)
  mixed=sine+.4*np.sin(2*np.pi*700*t)
  self.assertAlmostEqual(band(mixed,rate,440)/band(sine,rate,440),1,delta=.001)
  self.assertLess(band(sine,rate,700),band(sine,rate,440)*.00001)
  self.assertAlmostEqual(np.sqrt(band(sine*.13335,rate,440)/band(sine,rate,440)),.13335,places=5)
  pulsed=sine.copy();pulsed[:rate//4]=0
  self.assertAlmostEqual(band_level(pulsed,rate,440)/band_level(sine,rate,440),1,delta=.001)
 def test_frequency_and_envelope(self):
  rate=44100
  for frequency in (220,440,660):
   samples=np.sin(2*np.pi*frequency*np.arange(rate//3)/rate)
   self.assertAlmostEqual(spectrum(samples,rate),frequency,delta=.2)
  self.assertEqual(edges(np.array([False,True,True,False,True])),[(1,3),(4,5)])
 def test_short_signal_rejected(self):
  with self.assertRaises(ValueError):spectrum(np.zeros(100),44100)
 def test_compressed_decoder_padding_uses_original_not_nominal_length(self):
  for kind in ('ogg','mp3','wma'):
   old={'format':kind,'pitch':100,'spectral_peak_hz':440.,'complete_envelope_lengths_seconds':[1.06]}
   self.assertTrue(check_phase(old,old)['passed'])
   self.assertFalse(check_phase(old,dict(old,complete_envelope_lengths_seconds=[]))['passed'])
   self.assertFalse(check_phase(old,dict(old,complete_envelope_lengths_seconds=[1.12]))['passed'])
   self.assertFalse(check_phase(old,dict(old,spectral_peak_hz=450.))['passed'])
   with self.assertRaises(ValueError):check_phase(old,dict(old,format='wav'))
  with self.assertRaises(ValueError):check_phase(dict(old,format='unknown'),dict(old,format='unknown'))
  wma={'format':'wma','pitch':50,'spectral_peak_hz':440.,'complete_envelope_lengths_seconds':[1.06]}
  self.assertTrue(check_phase(wma,wma)['passed'])
  self.assertFalse(check_phase(wma,dict(wma,spectral_peak_hz=220.,complete_envelope_lengths_seconds=[2.12]))['passed'])
 def test_packet_timestamp_preserves_initial_silence(self):
  root=Path(__file__).resolve().parents[1]/'build/test-runtime-audio';root.mkdir(parents=True,exist_ok=True)
  with tempfile.TemporaryDirectory(dir=root) as directory:
   folder=Path(directory);rate=44100;audio=np.zeros(rate*6)
   for start in (.5,1.75,3.,4.25,5.5):
    begin=int(start*rate);end=min(int((start+1)*rate),int(5.7*rate))
    audio[begin:end]=.2*np.sin(2*np.pi*440*np.arange(end-begin)/rate)
   with wave.open(str(folder/'output.wav'),'wb') as output:
    output.setparams((2,2,rate,0,'NONE','not compressed'))
    output.writeframes(np.repeat((audio*32767).astype('<i2'),2).tobytes())
   report={'passed':True,'dll_sha256':'fixture','source_sha256':'fixture','case':{'format':'mid','pitch':100},'capture':{'discontinuities':0,'timestamp_errors':0,'first_packet_epoch_seconds':1000.}}
   (folder/'summary.json').write_text(json.dumps(report))
   (folder/'audio-stages.csv').write_text('format,pitch,start,played,end\nmid,100,1000.3,1000.35,1005.7\n')
   phase=analyze(folder)['phases'][0]
   self.assertAlmostEqual(phase['first_onset_after_play_seconds'],.15,delta=.02)
   self.assertGreaterEqual(len(phase['complete_envelope_lengths_seconds']),3)
   json.dumps(phase)
 def test_repeated_note_loss_and_shortened_notes_are_not_certified(self):
  reference={'format':'mid','pitch':50,'spectral_peak_hz':880.,'complete_envelope_lengths_seconds':[1.]*4,'onset_intervals_seconds':[1.25]*4}
  self.assertTrue(check_phase(reference,reference)['passed'])
  self.assertTrue(check_phase(reference,dict(reference,onset_intervals_seconds=[1.3000000000000007]*4))['passed'])
  self.assertFalse(check_phase(reference,dict(reference,onset_intervals_seconds=[1.31]*4))['passed'])
  for lengths,intervals in [([1.2],[1.28]),([1.7,.75,.73],[2.13,.83,1.22]),([1.]*4,[1.25,1.25,1.34])]:
   observed=dict(reference,complete_envelope_lengths_seconds=lengths,onset_intervals_seconds=intervals)
   self.assertFalse(check_phase(reference,observed)['passed'])
  timed=dict(reference,first_onset_after_play_seconds=np.float64(.15))
  self.assertTrue(check_phase(timed,timed)['passed'])
  json.dumps(check_phase(timed,timed))
  self.assertFalse(check_phase(timed,dict(timed,first_onset_after_play_seconds=1.4))['passed'])
  self.assertTrue(check_phase(dict(timed,first_onset_after_play_seconds=.35),timed)['passed'])

if __name__=='__main__':unittest.main()
