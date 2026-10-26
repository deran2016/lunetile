"""Check the MMO's installed stock performance helper in an isolated native client."""
import argparse,hashlib,json,os,shutil,subprocess
from pathlib import Path
from smoke_test import ROOT,read,write,MAIN_ENTRY,stop
from prepare_example import digest

def verify(bundle,output):
 bundle,output=bundle.resolve(),output.resolve()
 if output.exists() or output.is_relative_to(bundle) or bundle.is_relative_to(output):raise ValueError('Use a new separate verification folder')
 client=output/'client';shutil.copytree(bundle/'client',client,ignore=shutil.ignore_patterns('ClientProfile','Saves','*.log'))
 path=client/'Data/Scripts.rxdata';entries=read(path.read_bytes());main=next(i for i,e in enumerate(entries) if e.name==b'Main')
 helper=next(e for e in entries if e.name==b'MMO_StockPerformance');source=entries[main].source();assert source.endswith(MAIN_ENTRY)
 path.write_bytes(write(entries,{main:source[:-len(MAIN_ENTRY)]+(ROOT/'tests/runtime_mmo_performance.rb').read_bytes()}))
 environment=os.environ.copy();environment['LUNETILE_TEST_BACKGROUND']='1';process=None
 try:
  process=subprocess.Popen([str(client/'Game.exe')],cwd=client,env=environment);process.wait(timeout=30)
  if process.returncode or not (client/'mmo-performance.json').is_file():raise RuntimeError((client/'rgssxp.log').read_text(encoding='utf-8',errors='replace')[-5000:])
  report=json.loads((client/'mmo-performance.json').read_text(encoding='utf-8'));assert report['passed']
  report.update(dll_sha256=digest(bundle/'client/Lunetile.dll'),scripts_sha256=digest(bundle/'client/Data/Scripts.rxdata'),helper_sha256=hashlib.sha256(helper.source()).hexdigest())
  (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');return report
 finally:stop(process)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('bundle',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();verify(a.bundle,a.output);print('MMO stock helper, idle Rect cache, eight attack/skill poses and offline-save exclusion PASS')
