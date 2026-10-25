"""Assemble a separate online example from an already converted, trusted XP project."""
import argparse,hashlib,json,shutil,subprocess,sys,tempfile,zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
EXAMPLE=ROOT/'example'
MAIN_ENTRY=b'LunetileMMO.run\n'
CLIENT_SCRIPTS=(('MMO_Network','mmo_network.rb'),('MMO_Character','mmo_character.rb'),
 ('MMO_Inventory','mmo_inventory.rb'),('MMO_UI','mmo_ui.rb'),('MMO_HUD','mmo_hud.rb'),('MMO_Chat','mmo_chat.rb'),('MMO_Combat','mmo_combat.rb'),('MMO_Windows','mmo_windows.rb'),('MMO_Equipment','mmo_equipment.rb'),('MMO_Skills','mmo_skills.rb'),('MMO_Particles','mmo_particles.rb'),('MMO_Entry','mmo_entry.rb'))
sys.path.insert(0,str(ROOT/'scripts'))
from rxdata import Entry,integer,read,string,write
from package_template import ASSETS
from migrate_project import read_project_ini

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare(project,output,server,ruby,runtime=None):
 project,output,server,ruby=[Path(p).resolve() for p in (project,output,server,ruby)]
 if not ruby.is_file():raise ValueError('Ruby helper not found: '+str(ruby))
 if not server.is_file():raise ValueError('Windows server executable not found: '+str(server))
 runtime=Path(runtime).resolve() if runtime else project/'Lunetile.dll'
 if not runtime.is_file():raise ValueError('Runtime DLL not found: '+str(runtime))
 if output.exists():raise ValueError('Output already exists; refusing to overwrite game data or accounts')
 if output.is_relative_to(project) or project.is_relative_to(output):raise ValueError('Source and output must be separate')
 ini=read_project_ini(project/'Game.ini')[0]
 if ini.get('Game','Library',fallback='').lower()!='lunetile.dll':raise ValueError('Source must already be converted to Lunetile.dll')
 if ini.get('RGSSXP','DataEncoding',fallback='').upper()!='UTF-8':raise ValueError('This example requires converted UTF-8 XP data')
 if ini.get('Game','Scripts',fallback='').replace('\\','/').lower()!='data/scripts.rxdata':raise ValueError('Expected Data/Scripts.rxdata')
 selected=[project/name for name in ('Game.exe','Game.ini','Game.rxproj','Lunetile.dll')]
 for folder,extensions in ASSETS.items():
  selected.extend(p for p in (project/folder).rglob('*') if p.is_file() and p.suffix.lower() in extensions)
 for path in selected:
  if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(project):raise ValueError('Invalid project input: '+str(path))
 before={p.relative_to(project).as_posix():digest(p) for p in selected}
 entries=read((project/'Data/Scripts.rxdata').read_bytes())
 mains=[i for i,e in enumerate(entries) if e.name==b'Main']
 if len(mains)!=1:raise ValueError('Expected exactly one Main script')
 stock_main=next(e.source() for e in read((ROOT/'template-xp/Data/Scripts.rxdata').read_bytes()) if e.name==b'Main').replace(b'\r\n',b'\n')
 original_main=entries[mains[0]].source().replace(b'\r\n',b'\n')
 if not original_main.endswith(stock_main):raise ValueError('Main must end with the reviewed stock XP Main; custom startup is not replaced')
 bootstrap=original_main[:-len(stock_main)]
 if any(e.name in {name.encode() for name,_ in CLIENT_SCRIPTS} for e in entries):
  raise ValueError('Online script names already exist; refusing to duplicate or overwrite them')
 added=[];used_ids={e.id for e in entries};ident=1
 for name,filename in CLIENT_SCRIPTS:
  while ident in used_ids:ident+=1
  compressed=zlib.compress((EXAMPLE/'client'/filename).read_bytes())
  raw=b'['+integer(3)+b'i'+integer(ident)+string(name.encode())+string(compressed)
  added.append(Entry(ident,name.encode(),compressed,raw));ident+=1
 combined=entries[:mains[0]]+added+entries[mains[0]:]
 scripts=write(combined,{mains[0]+len(added):bootstrap+MAIN_ENTRY})
 exported=subprocess.run([str(ruby),'--disable-gems',str(EXAMPLE/'tools/export_world.rb'),str(project),str(ROOT/'src/runtime/rpg_schema.json')],capture_output=True,text=True,encoding='utf-8',timeout=20)
 if exported.returncode:raise ValueError('World export failed: '+exported.stderr)
 world=json.loads(exported.stdout)
 output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='mmo-build-',dir=output.parent) as temporary:
  staging=Path(temporary)/'game';client=staging/'client';client.mkdir(parents=True)
  for path in selected:
   target=client/path.relative_to(project);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
  portal=client/'Graphics/Characters/Lunetile_Portal.png'
  if portal.exists():raise ValueError('Source already contains Lunetile_Portal.png; refusing to replace project assets')
  portal.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(EXAMPLE/'assets/Graphics/Characters/Lunetile_Portal.png',portal)
  for name in ('Graphics','Audio'):(client/name).mkdir(exist_ok=True)
  for name in ('LICENSE','README.txt'):
   if (project/name).is_file():shutil.copy2(project/name,client/name)
  if (project/'licenses').is_dir():shutil.copytree(project/'licenses',client/'licenses')
  else:
   shutil.copy2(ROOT/'LICENSE',client/'LICENSE');shutil.copytree(ROOT/'licenses',client/'licenses')
  (client/'Data/Scripts.rxdata').write_bytes(scripts)
  shutil.copy2(runtime,client/'Lunetile.dll')
  ini['Game']['Title']='Lunetile XP Online Village'
  with (client/'Game.ini').open('w',encoding='utf-8') as file:ini.write(file)
  shutil.copy2(EXAMPLE/'client/client.json',client/'client.json')
  server_out=staging/'server';(server_out/'data').mkdir(parents=True)
  shutil.copy2(server,server_out/'lunetile-mmo-server.exe')
  shutil.copy2(ROOT/'LICENSE',server_out/'LICENSE')
  shutil.copy2(EXAMPLE/'server/THIRD_PARTY.md',server_out/'THIRD_PARTY.md')
  shutil.copytree(EXAMPLE/'server/licenses',server_out/'licenses')
  shutil.copy2(EXAMPLE/'server/data/items.json',server_out/'data/items.json')
  for name in ('growth','skills','monsters','progression','services','particles'):shutil.copy2(EXAMPLE/f'server/data/{name}.json',server_out/f'data/{name}.json')
  # Preserve the hand-edited example definitions when they match this template's geometry.
  defaults={key:json.loads((EXAMPLE/'server/data'/f'{key}.json').read_text(encoding='utf-8')) for key in ('maps','npcs','server')}
  same_map=defaults['maps'][0]==world['maps'][0] and defaults['server']['spawn']==world['server']['spawn']
  compatible=all(defaults['maps'][0][k]==world['maps'][0][k] for k in ('id','width','height','passages')) and defaults['server']['spawn']==world['server']['spawn']
  if compatible:
   expanded=subprocess.run([str(ruby),'--disable-gems',str(EXAMPLE/'tools/expand_maps.rb'),str(client),str(EXAMPLE/'server/data/world_layouts.json'),str(ROOT/'src/runtime/rpg_schema.json')],capture_output=True,text=True,encoding='utf-8',timeout=20)
   if expanded.returncode:raise ValueError('Expanded map generation failed: '+expanded.stderr)
  else:raise ValueError('Expanded example requires the reviewed starting map; export its portals and layouts before using another project')
  for key in ('maps','server','npcs'):
   data=([world['maps'][0]]+defaults['maps'][1:]) if key=='maps' else defaults[key] if same_map else world[key]
   (server_out/'data'/f'{key}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  shutil.copy2(EXAMPLE/'README.md',staging/'README.md')
  shutil.copy2(EXAMPLE/'DESIGN.md',staging/'DESIGN.md')
  shutil.copy2(EXAMPLE/'VALIDATION.md',staging/'VALIDATION.md')
  shutil.copy2(EXAMPLE/'PARTICLES.md',staging/'PARTICLES.md')
  shutil.copy2(EXAMPLE/'PERFORMANCE.md',staging/'PERFORMANCE.md')
  shutil.copy2(EXAMPLE/'ACCOUNTS.md',staging/'ACCOUNTS.md')
  shutil.copy2(EXAMPLE/'assets/ART_ASSETS.md',staging/'ART_ASSETS.md')
  (staging/'Start Server.cmd').write_bytes(b'@echo off\r\ncd /d "%~dp0server"\r\nlunetile-mmo-server.exe\r\nif errorlevel 1 echo Read the error above. For storage errors, fix the cause then run Recover Server.cmd.\r\npause\r\n')
  (staging/'Recover Server.cmd').write_bytes(b'@echo off\r\ncd /d "%~dp0server"\r\nlunetile-mmo-server.exe --recover-only\r\npause\r\n')
  (staging/'Start Client.cmd').write_bytes(b'@echo off\r\ncd /d "%~dp0client"\r\nstart "" Game.exe\r\n')
  (staging/'build-info.json').write_text(json.dumps({'source_sha256':before,'server_sha256':digest(server),'client_dll_sha256':digest(runtime),'changed_script':'Main','added_scripts':[name for name,_ in CLIENT_SCRIPTS],'protocol':11,'scope':'Converted XP starting map; Windows x64 Rust server and x86 client; requires XP Standard RTP'},indent=2)+'\n',encoding='utf-8')
  if before!={p.relative_to(project).as_posix():digest(p) for p in selected}:raise ValueError('Source project changed while preparing')
  hashes={p.relative_to(staging).as_posix():digest(p) for p in sorted(staging.rglob('*')) if p.is_file()}
  (staging/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
  staging.rename(output)
 return hashes

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('project',type=Path);parser.add_argument('output',type=Path)
 parser.add_argument('--server',type=Path,default=EXAMPLE/'server/target/x86_64-pc-windows-msvc/release/lunetile-mmo-server.exe')
 parser.add_argument('--ruby',type=Path,default=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe')
 parser.add_argument('--runtime',type=Path,default=ROOT/'build/runtime-native/bin/Release/Lunetile.dll')
 args=parser.parse_args()
 hashes=prepare(args.project,args.output,args.server,args.ruby,args.runtime)
 print(f'Online example ready: {args.output} ({len(hashes)} files; source unchanged)')
