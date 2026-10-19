"""Bounded manual review of an already migrated local project copy."""
import argparse,subprocess
from pathlib import Path
from test_runtime import ORIGINAL_EXE,ORIGINAL_DLL,sha

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path)
 a=ap.parse_args();project=a.project.resolve()
 if sha(project/'Game.exe')!=ORIGINAL_EXE or sha(project/'Lunetile.dll')==ORIGINAL_DLL:
  raise ValueError('Expected an unchanged launcher and independently built DLL')
 process=subprocess.Popen([str(project/'Game.exe')],cwd=project)
 print(f'PID={process.pid} project={project}',flush=True)
 try:process.wait(timeout=300)
 finally:
  if process.poll() is None:process.terminate();process.wait()
 print('Exit='+str(process.returncode),flush=True)

if __name__=='__main__':main()
