"""Verify build outputs and the supplied template launcher."""
import argparse,json,subprocess,sys
from pathlib import Path
from inspect_runtime import inspect

ROOT=Path(__file__).resolve().parents[1]

def verify(output):
 output.mkdir(parents=True,exist_ok=False)
 report={'passed':False,'scope':'CI build and launcher checks; no full gameplay, rendering or audio acceptance','steps':[]}
 try:
  gate=json.loads((ROOT/'build/runtime-ruby-x86/patched-4.0.7/gate.json').read_text(encoding='utf-8-sig'))
  if gate.get('passed') is not True:raise ValueError('Ruby build gate did not pass')
  artifact=inspect(ROOT/'build/runtime-native/bin/Release/RGSS104E.dll')
  report['runtime_sha256']=artifact['sha256']
  report['source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
  steps=[
   ('unit',[sys.executable,'-X','utf8','-B','-m','unittest','discover','-s','tests','-v']),
   ('interpreter',[str(ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'),'--disable-gems','tests/runtime_ruby.rb']),
   ('launcher',[sys.executable,'-X','utf8','-B','scripts/test_runtime.py','template/Game.exe',str(ROOT/'build/runtime-native/bin/Release/RGSS104E.dll'),str(output/'launcher-smoke')]),
  ]
  for name,command in steps:
   with (output/(name+'.log')).open('w',encoding='utf-8') as log:
    result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=180)
   report['steps'].append({'name':name,'exit_code':result.returncode})
   if result.returncode:raise RuntimeError(name+' failed; see '+str(output/(name+'.log')))
  report['launcher_skipped']=json.loads((output/'launcher-smoke/skipped.json').read_text(encoding='utf-8'))
  (output/'artifact.json').write_text(json.dumps(artifact,indent=2)+'\n',encoding='utf-8')
  report['passed']=True
 finally:
  (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('output',type=Path)
 args=parser.parse_args()
 verify(args.output.resolve())
 print('CI build checks PASS; gameplay acceptance was not run.')
