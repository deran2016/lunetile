"""Check stock controls, transactional saves, recovery and restart in isolated projects."""
import argparse,json,shutil
from pathlib import Path
from benchmark_stock_scripts import source
from verify_runtime import launch,prepare_projects
from runtime_validation import ROOT,DLLS,digest

def verify(engine,runtime,project,out):
 prefix=source(project,engine)
 options=dict(data=project/'Data',rtp=False,timeout=90)
 options.update(dict(screen_size=(1280,720),timing_profile='stock120') if engine=='xp' else dict(high=True,wide=True))
 first=out/'write'
 launch(engine,runtime,first,prefix+(ROOT/'tests/runtime_comfort.rb').read_bytes(),**options)
 read=b"""
c=Lunetile::Controls;f=Lunetile::Comfort
raise 'Restart controls' unless c.binding(:confirm)==[[86],:rt] && !c.rumble_enabled?
f.load(f.auto_path+'.bak1')
raise 'Restart autosave' unless $game_variables[1]==910
manual=f.vxa? ? LunetileVXA.slot(0,true) : RGSSXP::Saves.filename(0,:write)
f.load(manual+'.bak1')
raise 'Restart backup' unless $game_variables[1]==4
File.write('runtime-complete.txt','restart comfort,false,false')
"""
 launch(engine,runtime,out/'restart',prefix+read,saves=first/'Saves',**options)
 corrupt=out/'corrupt-settings';shutil.copytree(first/'Saves',corrupt)
 for name in ['controls','comfort']:(corrupt/f'Lunetile/{name}.json').write_text('{broken',encoding='utf-8')
 invalid=b"""
raise 'Invalid controls did not use defaults' unless Lunetile::Controls.binding(:confirm)==[[32,90,13],:a] && Lunetile::Controls.load_error
raise 'Invalid autosave settings did not use defaults' unless Lunetile::Comfort.enabled? && Lunetile::Comfort.error
raise 'Invalid settings overwritten' unless File.binread(Lunetile::Controls::PATH)=='{broken' && File.binread(Lunetile::Comfort::PATH)=='{broken'
File.write('runtime-complete.txt','invalid settings preserved,false,false')
"""
 launch(engine,runtime,out/'invalid-settings',prefix+invalid,saves=corrupt,**options)
 backend=(ROOT/'tests/runtime_controls_backend.rb').read_text().replace('__PROBE_DLL__',(runtime/'LunetileXInputProbe.dll').as_posix()).encode()
 launch(engine,runtime,out/'xinput-backend',backend,timeout=30,**(dict(timing_profile='stock120') if engine=='xp' else dict(high=True)))
 if (out/'xinput-backend/xinput-motors.txt').read_text()!='0,0':raise AssertionError('Shutdown did not stop simulated motors')
 report=dict(passed=True,engine=engine,runtime_sha256=digest(runtime/DLLS[engine]),probe_sha256=digest(runtime/'LunetileXInputProbe.dll'),checks=['bindings-validation','rumble-validation','backup-rotation','failed-replacement','safe-autosave','manual-and-autosave-recovery','failed-load-rollback','restart','invalid-settings-preserved','simulated-xinput-mapping-rumble-timeout-focus-F12-shutdown'],physical_gamepad=False,rtp_required=False)
 (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 return report

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('output',type=Path)
 ap.add_argument('--runtime',type=Path,default=ROOT/'build/runtime-native/bin/Release')
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 projects=prepare_projects(a.runtime.resolve(),out/'projects',DLLS)
 rows=[verify(e,a.runtime.resolve(),projects/e,out/e) for e in DLLS]
 (out/'summary.json').write_text(json.dumps(dict(passed=all(r['passed'] for r in rows),results=rows),indent=2)+'\n')
 print('XP/VXA controls, autosaves, three backups, recovery, restart PASS')

if __name__=='__main__':main()
