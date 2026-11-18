"""Prepare isolated stock-map scenes for manual Discord overlay verification."""
import argparse
from pathlib import Path
import runtime_validation as policy

ROOT=policy.ROOT
MANUAL_CHECKS=['open-close','pinned-widget','text-input-isolation','gamepad-input-isolation',
 'focus-return','resize-maximize','borderless','f12-restart','browser-interaction','pinned-performance']

def install_review(project,engine,wide):
 from benchmark_stock_scripts import source,render_probe
 from test_runtime import scripts
 from migrate_project import read_project_ini
 ext='rxdata' if engine=='xp' else 'rvdata2'
 setup,_=render_probe(engine)
 body=source(project,engine)+f'\nREVIEW_ENGINE={engine!r}\nREVIEW_WIDE={str(wide).lower()}\n'.encode()+setup.encode()+(ROOT/'tests/runtime_discord_review.rb').read_bytes()
 (project/f'Review.{ext}').write_bytes(scripts(body))
 ini,encoding=read_project_ini(project/'Game.ini')
 ini.set('Game','Scripts',f'Review.{ext}')
 ini.set('Game','Title',f'Lunetile Discord Review {engine} {"wide" if wide else "default"}')
 with (project/'Game.ini').open('w',encoding=encoding) as stream:ini.write(stream,space_around_delimiters=False)
 return dict(engine=engine,size=[1280,720] if wide else [640,480] if engine=='xp' else [544,416],
  launcher=str((project/'Game.exe').resolve()),dll_sha256=policy.digest(project/policy.DLLS[engine]),
  checks={name:dict(status='not_verified',reason='Requires actual Discord overlay and manual observation') for name in MANUAL_CHECKS})

def prepare(runtime,output):
 from verify_runtime import prepare_projects
 from migrate_project import migrate
 runtime=Path(runtime).resolve();output=Path(output).resolve()
 for source in [ROOT/'template-xp',ROOT/'template-vxa',runtime]:
  if output.is_relative_to(source) or source.is_relative_to(output):raise ValueError('Separate output directory required')
 if output.exists():raise ValueError('Output already exists; refusing to overwrite')
 policy.check_build(runtime);output.mkdir(parents=True)
 projects=prepare_projects(runtime,output/'projects',list(policy.DLLS))
 cases={}
 for engine,name in policy.DLLS.items():
  native=output/(engine+'-default')
  migrate(projects/(engine+'-source'),native,runtime/name,runtime/'rgssxp-ruby.exe',data_encoding='UTF-8',engine=engine)
  cases[engine+'-default']=install_review(native,engine,False)
  cases[engine+'-wide']=install_review(projects/engine,engine,True)
 report=dict(prepared=True,overlay_passed=False,discord_version=None,overlay_settings=None,cases=cases,
  scope='Manual Discord compatibility only. Preparation, mock focus checks and engine screenshots do not certify overlay support. No Discord settings/accounts are read or modified.')
 policy.write_json(output/'discord-review.json',report)
 return report

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('output',type=Path)
 ap.add_argument('--runtime',type=Path,default=ROOT/'build/runtime-native/bin/Release')
 args=ap.parse_args();report=prepare(args.runtime,args.output)
 for name,row in report['cases'].items():print(name,row['launcher'])
 print('Prepared; Discord overlay compatibility remains NOT VERIFIED.')

if __name__=='__main__':main()
