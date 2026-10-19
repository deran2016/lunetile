"""Observe only the exact copied replacement PID while the waveform controller runs separately."""
import argparse,hashlib,json,threading,time
from pathlib import Path
import frida
from capture_original_audio import ROOT,process_path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('project',type=Path);a=ap.parse_args()
 project=a.project.resolve();project.relative_to((ROOT/'build').resolve())
 expected=sha(ROOT/'build/runtime-native/bin/Release/Lunetile.dll')
 device=frida.get_local_device();deadline=time.monotonic()+60;pid=None
 while time.monotonic()<deadline:
  for process in device.enumerate_processes():
   if process.name.lower()=='game.exe':
    try:
     if process_path(process.pid)==project/'Game.exe':pid=process.pid;break
    except OSError:pass
  if pid is not None:break
  time.sleep(.1)
 if pid is None:raise TimeoutError('Owned waveform process did not appear')
 assert sha(project/'Game.exe')=='0ed9b5139edb0ad0f0f4b5b88dd0265ddbf56d36d6f173d6a22f3b23e8212e22' and sha(project/'Lunetile.dll')==expected
 if (project/'midi-timing.jsonl').exists():raise FileExistsError('Timing output already exists')
 source=(ROOT/'scripts/trace_runtime_midi.js').read_text();messages=[];ended=threading.Event()
 session=device.attach(pid);session.on('detached',lambda *args:ended.set());script=session.create_script(source)
 script.on('message',lambda message,data:messages.append(message))
 try:script.load();ended.wait(40)
 finally:
  if not ended.is_set():script.unload();session.detach()
 report={'provider':'Passive Python Frida; separate diagnostic, not benchmark or REA evidence','version':frida.__version__,'pid':pid,'dll_sha256':expected,'observer_sha256':hashlib.sha256(source.encode()).hexdigest(),'messages':messages}
 (project/'midi-timing-capture.json').write_text(json.dumps(report,indent=2))
 assert not any(message.get('type')=='error' for message in messages),messages
 assert (project/'midi-timing.jsonl').exists()
 print('Owned MIDI timing trace complete')

if __name__=='__main__':main()
