"""Capture only the isolated game PID tree; generated tones, never microphone or endpoint-wide audio."""
import argparse,hashlib,json,math,shutil,struct,subprocess,time,wave
from pathlib import Path
import psutil
from test_runtime import ROOT,ORIGINAL_EXE,ORIGINAL_DLL,sha,scripts

def fixtures(data,channels=False,compressed=False):
 data.mkdir()
 with wave.open(str(data/'sustain.wav'),'wb') as stream:
  stream.setparams((1,2,44100,0,'NONE','not compressed'))
  stream.writeframes(b''.join(struct.pack('<h',int(5000*math.sin(2*math.pi*440*i/44100))) for i in range(44100)))
 # Organ note A4 held for 960 ticks at 480 PPQN / 120 BPM; 1.0 seconds before resampling.
 track=b'\x00\xff\x51\x03\x07\xa1\x20\x00\xc0\x13\x00\x90\x45\x60\x87\x40\x80\x45\x00\x81\x70\xff\x2f\x00'
 (data/'sustain.mid').write_bytes(b'MThd'+struct.pack('>IHHH',6,0,1,480)+b'MTrk'+struct.pack('>I',len(track))+track)
 if compressed:
  ffmpeg=shutil.which('ffmpeg')
  if not ffmpeg:raise RuntimeError('Compressed audio fixtures require installed ffmpeg; it is not a runtime dependency')
  for extension,codec in [('ogg','libvorbis'),('mp3','libmp3lame'),('wma','wmav2')]:
   subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-i',str(data/'sustain.wav'),'-c:a',codec,str(data/('sustain.'+extension))],check=True)
 if channels:
  with wave.open(str(data/'bgs.wav'),'wb') as stream:
   stream.setparams((1,2,44100,0,'NONE','not compressed'))
   stream.writeframes(b''.join(struct.pack('<h',int(5000*math.sin(2*math.pi*700*i/44100))) for i in range(44100)))
  for name,note,hold,tail in [('held.mid',69,b'\xf8\x00',b'\x83\x60'),('me.mid',71,b'\x84\x40',b'\x81\x40')]:
   track=b'\x00\xff\x51\x03\x07\xa1\x20\x00\xc0\x13\x00\x90'+bytes([note,96])+hold+b'\x80'+bytes([note,0])+tail+b'\xff\x2f\x00'
   (data/name).write_bytes(b'MThd'+struct.pack('>IHHH',6,0,1,480)+b'MTrk'+struct.pack('>I',len(track))+track)

def capture(exe,dll,tool,out,phase,data=None):
 if phase not in [(f,p) for f in ('wav','mid') for p in (50,100,150)]+[('sequence',100),('compressed',100),('wma-roles',100),('channels',100),('channels-held',100),('channels-repeat',100),('volumes',100)]:raise ValueError('Unknown audio calibration case')
 assert sha(exe)==ORIGINAL_EXE
 out.mkdir(parents=True,exist_ok=False)
 shutil.copy2(exe,out/'Game.exe');shutil.copy2(dll,out/'RGSS104E.dll')
 runtime_hash=sha(out/'RGSS104E.dll')
 if data:shutil.copytree(data,out/'Data')
 else:fixtures(out/'Data',phase[0].startswith('channels') or phase[0]=='volumes',phase[0] in ('compressed','wma-roles'))
 source=(ROOT/'tests'/('rgss_wma_roles_reference.rb' if phase[0]=='wma-roles' else 'runtime_audio_volumes.rb' if phase[0]=='volumes' else 'runtime_audio_channels.rb' if phase[0].startswith('channels') else 'runtime_audio_waveform.rb')).read_bytes();tool_hash=sha(tool)
 (out/'Scripts.rxdata').write_bytes(scripts(source))
 (out/'audio-case.txt').write_text(phase[0]+','+str(phase[1]))
 (out/'Game.ini').write_text('[Game]\nLibrary=RGSS104E.dll\nScripts=Scripts.rxdata\nTitle=RGSSXP process audio diagnostic\nRTP1=\nRTP2=\nRTP3=\n')
 game=subprocess.Popen([str(out/'Game.exe')],cwd=out)
 images={};recorder=None
 try:
  deadline=time.monotonic()+15
  while time.monotonic()<deadline:
   if game.poll() is not None:raise RuntimeError('Game ended before capture activation')
   for item in psutil.Process(game.pid).memory_maps():
    path=Path(item.path)
    if path.suffix.lower() in ('.exe','.dll') and path.is_file():images[str(path)]=sha(path)
   if str(out/'RGSS104E.dll') in images:break
   time.sleep(.05)
  assert images.get(str(out/'RGSS104E.dll'))==runtime_hash
  assert not any(Path(name).name.lower()=='rgssframepacing.dll' for name in images)
  if runtime_hash!=ORIGINAL_DLL:assert ORIGINAL_DLL not in images.values()
  print('Waiting for initial test frame: '+str(out),flush=True)
  deadline=time.monotonic()+120
  while not (out/'game-ready.txt').exists():
   if game.poll() is not None:raise RuntimeError('Game ended before its initial test frame')
   if time.monotonic()>deadline:raise TimeoutError('Test window initial frame was not dispatched; activate the owned game window')
   time.sleep(.05)
  seconds=45 if phase[0] in ('sequence','compressed') else 30
  recorder=subprocess.Popen([str(tool),str(game.pid),str(seconds),str(out/'output.wav'),str(out/'capture-ready.txt')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  stdout,stderr=recorder.communicate(timeout=seconds+15)
  (out/'capture-stdout.txt').write_text(stdout);(out/'capture-stderr.txt').write_text(stderr)
  if recorder.returncode:raise RuntimeError('Process audio capture failed: '+stderr)
  game.wait(timeout=10)
  assert game.returncode==0 and (out/'runtime-complete.txt').exists()
  stats=json.loads(stdout);assert stats['bytes']>0 and stats['packets']>0
  if not stats.get('target_exited'):raise RuntimeError('Capture deadline elapsed before the owned game exited; incomplete probe')
  assert sha(out/'RGSS104E.dll')==runtime_hash
  assert sha(tool)==tool_hash
  result={'passed':True,'case':{'format':phase[0],'pitch':phase[1]},'dll_sha256':runtime_hash,'capture_tool_sha256':tool_hash,'source_sha256':hashlib.sha256(source).hexdigest(),'fixtures':{name:sha(out/'Data'/name) for name in ('sustain.wav','sustain.mid')},'capture':stats,'scope':'Process-tree PCM acquisition only; waveform analysis and fidelity verdict separate; MIDI uses identical Graphics.update dispatch. Capture starts after initial frame readiness; foreground waits are not latency measurements.'}
  if phase[0]=='sequence':del result['case'];result['scenario']='Same-process pitch changes and MIDI teardown'
  if phase[0]=='compressed':del result['case'];result['scenario']='Same-process compressed tone pitch changes'
  if phase[0].startswith('channels') or phase[0] in ('volumes','compressed','wma-roles'):result['fixtures']={p.name:sha(p) for p in sorted((out/'Data').iterdir())}
  (out/'summary.json').write_text(json.dumps(result,indent=2))
  return result
 finally:
  if recorder and recorder.poll() is None:recorder.terminate();recorder.wait()
  if game.poll() is None:game.terminate();game.wait()
  (out/'modules.json').write_text(json.dumps(images,indent=2))
  (out/'process-result.json').write_text(json.dumps({'pid':game.pid,'exit_code':game.returncode,'dll_sha256':runtime_hash,'capture_exit_code':recorder.returncode if recorder else None},indent=2))

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('project',type=Path);ap.add_argument('original',type=Path);ap.add_argument('replacement',type=Path);ap.add_argument('output',type=Path)
 mode=ap.add_mutually_exclusive_group()
 mode.add_argument('--sequence',action='store_true',help='Keep all six phases in one process to check pitch changes and output teardown')
 mode.add_argument('--compressed',action='store_true',help='Compare generated Ogg/MP3/WMA tones at three pitches in one process')
 mode.add_argument('--wma-roles',action='store_true',help='Compare original WMA pitch semantics in all four audio roles')
 mode.add_argument('--channels',action='store_true',help='Capture MIDI BGM/ME with an independent WAV BGS, volume changes and resume')
 mode.add_argument('--volumes',action='store_true',help='Measure six MIDI AudioPath volume values using held-note PCM')
 a=ap.parse_args();assert sha(a.original)==ORIGINAL_DLL
 if sha(a.replacement)==ORIGINAL_DLL:raise ValueError('Replacement must be the independently built DLL')
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 if a.compressed or a.wma_roles:fixtures(out/'fixtures',compressed=True)
 tool=ROOT/'build/runtime-native/bin/Release/process_audio_capture.exe'
 results={}
 for name,dll in [('original',a.original),('replacement',a.replacement)]:
  if a.wma_roles:
   print('Capturing WMA BGM/BGS/ME/SE pitch cases: '+name,flush=True)
   results[name]=capture((a.project/'Game.exe').resolve(),dll.resolve(),tool,out/name,('wma-roles',100),out/'fixtures')
   continue
  if a.compressed:
   print('Capturing same-process compressed tone sequence: '+name,flush=True)
   results[name]=capture((a.project/'Game.exe').resolve(),dll.resolve(),tool,out/name,('compressed',100),out/'fixtures')
   continue
  if a.volumes:
   print('Capturing physical MIDI volume steps: '+name,flush=True)
   results[name]=capture((a.project/'Game.exe').resolve(),dll.resolve(),tool,out/name,('volumes',100))
   continue
  if a.channels:
   (out/name).mkdir();results[name]={}
   for pattern in ('held','repeat'):
    print('Capturing channels '+name+' '+pattern,flush=True)
    results[name][pattern]=capture((a.project/'Game.exe').resolve(),dll.resolve(),tool,out/name/pattern,('channels-'+pattern,100))
   continue
  if a.sequence:
   print('Capturing same-process pitch sequence: '+name,flush=True)
   results[name]=capture((a.project/'Game.exe').resolve(),dll.resolve(),tool,out/name,('sequence',100))
   continue
  (out/name).mkdir();results[name]=[]
  for phase in [(f,p) for f in ('wav','mid') for p in (50,100,150)]:
   print('Capturing generated tone: '+name+' '+str(phase),flush=True)
   results[name].append(capture((a.project/'Game.exe').resolve(),dll.resolve(),tool,out/name/(phase[0]+'-'+str(phase[1])),phase))
 (out/'summary.json').write_text(json.dumps(results,indent=2))
 print('Process-specific audio acquisition: PASS; analysis still required')

if __name__=='__main__':main()
