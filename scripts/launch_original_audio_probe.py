"""Run original RGSS with one generated MIDI while an explicitly armed REA trace observes it."""
import argparse,shutil,subprocess
from pathlib import Path
from test_runtime import ROOT,scripts,sha,ORIGINAL_DLL,ORIGINAL_EXE
from test_runtime_audio import fixtures

def main():
 ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('output',type=Path)
 ap.add_argument('--source',type=Path,default=ROOT/'tests/rgss_midi_pitch_reference.rb')
 ap.add_argument('--prepare-only',action='store_true',help='Prepare files for a trace that spawns the process suspended')
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 assert sha(a.exe)==ORIGINAL_EXE and sha(a.dll)==ORIGINAL_DLL
 shutil.copy2(a.exe,out/'Game.exe');shutil.copy2(a.dll,out/'RGSS104E.dll')
 fixtures(out/'Data')
 (out/'Scripts.rxdata').write_bytes(scripts(a.source.read_bytes()))
 (out/'Game.ini').write_text('[Game]\nLibrary=RGSS104E.dll\nScripts=Scripts.rxdata\nTitle=Original MIDI API Reference\nRTP1=\nRTP2=\nRTP3=\n')
 if a.prepare_only:
  print('Prepared '+str(out));return
 p=subprocess.Popen([str(out/'Game.exe')],cwd=out);print(f'PID={p.pid} output={out}',flush=True)
 try:p.wait(timeout=90)
 finally:
  if p.poll() is None:p.terminate();p.wait()
 print('Exit='+str(p.returncode),flush=True)

if __name__=='__main__':main()
