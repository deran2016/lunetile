"""Reproduce the implemented runtime gates; this does not certify gameplay."""
import argparse,json,subprocess,sys
from pathlib import Path
from test_runtime import ROOT,sha
from rxdata import read

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('project',type=Path);ap.add_argument('original_dll',type=Path);ap.add_argument('save',type=Path);ap.add_argument('output',type=Path)
 ap.add_argument('--dll',type=Path,default=ROOT/'build/runtime-native/bin/Release/RGSS104E.dll')
 ap.add_argument('--ruby',type=Path,default=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe')
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 project,original,dll,save,ruby=[p.resolve() for p in (a.project,a.original_dll,a.dll,a.save,a.ruby)]
 originals=[project/'Game.exe',project/'Data/Scripts.rxdata',original,save]
 before={str(path):sha(path) for path in originals}
 steps=[
  ('unit',[sys.executable,'-m','unittest','discover','-s','tests','-v']),
  ('interpreter',[str(ruby),'--disable-gems','tests/runtime_ruby.rb']),
  ('pe',[sys.executable,'scripts/inspect_runtime.py',str(dll),'--output',str(out/'artifact.json')]),
  ('runtime',[sys.executable,'scripts/test_runtime.py',str(project/'Game.exe'),str(dll),str(out/'smoke')]),
  ('file-io',[sys.executable,'scripts/test_runtime_file_io.py',str(project/'Game.exe'),str(dll),str(out/'file-io')]),
  ('data-and-import',[sys.executable,'scripts/test_runtime_import.py',str(project),str(original),str(dll),str(save),str(out/'import')]),
  ('archive',[sys.executable,'scripts/test_runtime_archive.py',str(project/'Game.exe'),str(original),str(dll),str(out/'archive')]),
  ('archive-names',[sys.executable,'scripts/test_runtime_archive_names.py',str(project/'Game.exe'),str(dll),str(out/'archive-names')]),
  ('archive-migration',[sys.executable,'scripts/test_archive_migration.py',str(project),str(original),str(dll),str(ruby),str(out/'archive-migration')]),
  ('migration-guards',[sys.executable,'scripts/test_migration_guards.py',str(project),str(dll),str(ruby),str(out/'migration-guards'),'--original-dll',str(original)]),
  ('migration-text',[sys.executable,'scripts/test_migration_text.py',str(project),str(dll),str(ruby),str(out/'migration-text'),'--original-dll',str(original)]),
  ('legacy-pacing',[sys.executable,'scripts/check_legacy_pacing_migration.py',str(project),str(dll),str(ruby),str(out/'legacy-pacing')]),
  ('graphics',[sys.executable,'scripts/test_runtime_graphics.py',str(project),str(original),str(dll),str(out/'graphics')]),
  ('graphics-extended',[sys.executable,'scripts/test_runtime_graphics_extended.py',str(project/'Game.exe'),str(original),str(dll),str(out/'graphics-extended')]),
  ('transition-counter',[sys.executable,'scripts/test_runtime_transition_counter.py',str(project/'Game.exe'),str(original),str(dll),str(out/'transition-counter')]),
  ('output-color-build',['cmake','--build',str(ROOT/'build/runtime-native'),'--config','Release','--target','runtime_output_color']),
  ('output-color',[str(ROOT/'build/runtime-native/bin/Release/runtime_output_color.exe')]),
  ('integer-order',[sys.executable,'scripts/test_runtime_order.py',str(project),str(original),str(dll),str(out/'integer-order')]),
  ('audio-decoder-build',['cmake','--build',str(ROOT/'build/runtime-native'),'--config','Release','--target','audio_decode_probe']),
  ('audio-decoder',[str(ROOT/'build/runtime-native/bin/Release/audio_decode_probe.exe')]),
  ('audio',[sys.executable,'scripts/test_runtime_audio.py',str(project/'Game.exe'),str(dll),str(out/'audio')]),
  ('reset',[sys.executable,'scripts/test_runtime_reset.py',str(project/'Game.exe'),str(original),str(dll),str(out/'reset')]),
  ('migration',[sys.executable,'scripts/migrate_project.py',str(project),str(out/'project'),'--dll',str(dll),'--ruby',str(ruby)]),
 ]
 report={'passed':False,'scope':'Ruby/ABI/data/import/archive/migration/primitive graphics/audio voice gates; gameplay and sound fidelity not certified','runtime_sha256':sha(dll),'steps':[]}
 try:
  for label,command in steps:
   print('Checking '+label,flush=True)
   with (out/(label+'.log')).open('w',encoding='utf-8') as log:
    result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,encoding='utf-8',timeout=180)
   report['steps'].append({'name':label,'exit_code':result.returncode})
   if result.returncode:raise RuntimeError(f'{label} failed; see {out/(label+".log")}')
  old=read((project/'Data/Scripts.rxdata').read_bytes());new=read((out/'project/Data/Scripts.rxdata').read_bytes())
  if [(e.id,e.name) for e in old]!=[(e.id,e.name) for e in new]:raise RuntimeError('Migration changed script identity/order')
  manifest=json.loads((out/'project/migration/manifest.json').read_text(encoding='utf-8'))
  changed={entry['index'] for entry in manifest['scripts'] if entry['changes']}
  if any(left.raw!=right.raw for index,(left,right) in enumerate(zip(old,new)) if index not in changed):raise RuntimeError('Migration changed an untouched entry')
  # Existing output rejection must leave the completed copy unchanged.
  rejected=subprocess.run(steps[-1][1],cwd=ROOT,capture_output=True)
  if rejected.returncode==0:raise RuntimeError('Migration overwrote an existing output')
  if before!={str(path):sha(path) for path in originals}:raise RuntimeError('An original file changed')
  report['originals_preserved']=True;report['migration_changed_entries']=len(changed);report['migration_preserved_entries']=len(old)-len(changed)
  report['passed']=True
 finally:
  (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Implemented runtime gates PASS: '+str(out/'summary.json'))

if __name__=='__main__':main()
