"""Isolated native graphics review; stop via its own marker, with a bounded lifetime."""
import argparse,shutil,subprocess,time
from pathlib import Path
from test_runtime import scripts,sha,ORIGINAL_EXE,ORIGINAL_DLL

def main():
 ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('source',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--title',default='RGSS Graphics Review')
 ap.add_argument('--mode',choices=['debug','btest'])
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 assert sha(a.exe)==ORIGINAL_EXE
 library='RGSS104E.dll' if sha(a.dll)==ORIGINAL_DLL else 'Lunetile.dll'
 shutil.copy2(a.exe,out/'Game.exe');shutil.copy2(a.dll,out/library)
 (out/'Scripts.rxdata').write_bytes(scripts(a.source.read_bytes()))
 (out/'Game.ini').write_text(f'[Game]\nLibrary={library}\nScripts=Scripts.rxdata\nTitle={a.title}\nRTP1=\nRTP2=\nRTP3=\n')
 process=subprocess.Popen([str(out/'Game.exe')]+([a.mode] if a.mode else []),cwd=out)
 print(f'PID={process.pid} output={out}',flush=True)
 try:process.wait(timeout=300)
 finally:
  if process.poll() is None:process.terminate();process.wait()
 print('Exit='+str(process.returncode),flush=True)

if __name__=='__main__':main()
