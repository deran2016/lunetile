"""Isolated manual UI probe; native telemetry queries only its own HWND and never injects input."""
import argparse,json,shutil,subprocess,time
from pathlib import Path
import psutil
from test_runtime import ROOT,ORIGINAL_EXE,ORIGINAL_DLL,sha,scripts

def main():
 ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
 out=a.output.resolve();assert sha(a.exe)==ORIGINAL_EXE;out.mkdir(parents=True,exist_ok=False)
 shutil.copy2(a.exe,out/'Game.exe');shutil.copy2(a.dll,out/'RGSS104E.dll');(out/'Scripts.rxdata').write_bytes(scripts((ROOT/'tests/runtime_window_review.rb').read_bytes()))
 runtime_hash=sha(out/'RGSS104E.dll')
 (out/'Game.ini').write_text('[Game]\nLibrary=RGSS104E.dll\nScripts=Scripts.rxdata\nTitle=RGSSXP window review\nRTP1=\nRTP2=\nRTP3=\n')
 process=subprocess.Popen([str(out/'Game.exe')],cwd=out);print('Window review PID='+str(process.pid)+' '+str(out),flush=True)
 began=time.monotonic();images={}
 try:
  while process.poll() is None:
   if time.monotonic()-began>600:raise TimeoutError('Window UI review deadline exceeded')
   if not images and time.monotonic()-began>2:
    try:images={item.path:sha(Path(item.path)) for item in psutil.Process(process.pid).memory_maps() if Path(item.path).suffix.lower() in ('.dll','.exe') and Path(item.path).is_file()}
    except psutil.NoSuchProcess:pass
   time.sleep(.5)
 finally:
  if process.poll() is None:process.terminate();process.wait()
  (out/'modules.json').write_text(json.dumps(images,indent=2));(out/'process-result.json').write_text(json.dumps({'exit_code':process.returncode,'dll_sha256':runtime_hash,'scope':'Manual window actions; inspect trace and screenshots before claiming UI validation'},indent=2))
 assert sha(out/'RGSS104E.dll')==runtime_hash and images and runtime_hash in images.values()
 if runtime_hash!=ORIGINAL_DLL:assert ORIGINAL_DLL not in images.values()

if __name__=='__main__':main()
