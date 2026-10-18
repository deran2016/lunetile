"""Generated audio, actual output-voice progression and worker lifetime checks."""
import argparse,json,math,shutil,struct,subprocess,wave
from pathlib import Path
from test_runtime import ROOT,run,sha

def fixtures(out):
 out.mkdir()
 for name,seconds in [('tone',1),('short',.18)]:
  with wave.open(str(out/(name+'.wav')),'wb') as file:
   file.setparams((1,2,11025,0,'NONE','not compressed'))
   file.writeframes(b''.join(struct.pack('<h',int(2000*math.sin(2*math.pi*440*i/11025))) for i in range(int(11025*seconds))))
 ffmpeg=shutil.which('ffmpeg')
 if not ffmpeg:raise RuntimeError('Audio fixture generation requires an installed ffmpeg; it is not a runtime dependency')
 for extension,codec in [('ogg','libvorbis'),('mp3','libmp3lame'),('wma','wmav2')]:
  subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-i',str(out/'tone.wav'),'-c:a',codec,str(out/('tone.'+extension))],check=True)
 track=b'\x00\xff\x51\x03\x07\xa1\x20\x00\xc0\x00\x00\x90\x45\x30\x87\x40\x80\x45\x00\x00\xff\x2f\x00'
 (out/'tone.mid').write_bytes(b'MThd'+struct.pack('>IHHH',6,0,1,480)+b'MTrk'+struct.pack('>I',len(track))+track)
 drums=b'\x00\xc9\x00\x00\x99\x24\x30\x87\x40\x89\x24\x00\x00\xff\x2f\x00'
 (out/'drums.mid').write_bytes(b'MThd'+struct.pack('>IHHH',6,0,1,480)+b'MTrk'+struct.pack('>I',len(drums))+drums)
 (out/'bad.wav').write_bytes(b'RIFF\xff\xff\xff\xffWAVE')
 (out/'bad.ogg').write_bytes(b'OggSinvalid')
 (out/'bad.mid').write_bytes(b'MThd\x00\x00\x00\x06')
 (out/'bad.mp3').write_bytes(b'ID3invalid')
 return {p.name:sha(p) for p in out.iterdir()}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('output',type=Path)
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 hashes=fixtures(out/'input')
 result=run(a.exe.resolve(),a.dll.resolve(),out/'playback','',(ROOT/'tests/runtime_audio.rb').read_bytes(),data=out/'input')
 (out/'summary.json').write_text(json.dumps({'passed':True,'scope':'Actual source-voice progression; no acoustic or original sound-waveform comparison yet','fixtures':hashes,'run':result},indent=2))
 print('Generated WAV/Vorbis/MP3/WMA/MIDI, worker playback and stop/fade/ME/loop guards: PASS')

if __name__=='__main__':main()
