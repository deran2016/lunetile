"""Primitive API, source definitions and hardware rendering checks; not gameplay completion."""
import argparse,ast,json,shutil,subprocess,sys
from pathlib import Path
from test_runtime import ROOT,run

def records(path):
 result={}
 for line in path.read_text().splitlines():
  name,value=line.split('\t',1)
  result[name]=ast.literal_eval(value.replace('nil','None').replace('true','True').replace('false','False'))
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);ap.add_argument('original_dll',type=Path);ap.add_argument('replacement_dll',type=Path);ap.add_argument('output',type=Path)
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 exe=(a.project/'Game.exe').resolve();dll=a.replacement_dll.resolve();results=[]
 for case,probe in [('constructors','rgss_constructor_reference.rb'),('primitives','rgss_graphics_reference.rb'),('alpha','rgss_bitmap_alpha_reference.rb'),('effects','rgss_sprite_effects_reference.rb')]:
  command=[sys.executable,str(ROOT/'scripts/probe_original_types.py'),str(exe),str(a.original_dll.resolve()),str(out/(case+'-original')),'--probe',str(ROOT/'tests'/probe)]
  with (out/(case+'.log')).open('w') as log:subprocess.run(command,cwd=ROOT,check=True,stdout=log,stderr=subprocess.STDOUT)
  source=(ROOT/'tests'/probe).read_bytes()+b"\nFile.write('runtime-complete.txt','graphics,false,false'); sleep 0.5\n"
  result=run(exe,dll,out/(case+'-new'),'',source)
  before=records(out/(case+'-original/types-reference.txt'));after=records(out/(case+'-new/types-reference.txt'))
  # Internal Ruby ivar names are diagnostic only; compare the observable damage child states.
  if case=='effects':before.pop('damage_fields');after.pop('damage_fields')
  differences=[key for key in before if before[key]!=after.get(key)]
  assert not differences,{'differences':differences}
  results.append({'case':case,'matching_records':len(before),'runtime':result})
 fixture=out/'input';fixture.mkdir();shutil.copy2(a.project/'Data/Scripts.rxdata',fixture/'StockScripts.rxdata')
 results.append({'case':'definitions','runtime':run(exe,dll,out/'definitions','',(ROOT/'tests/runtime_script_definitions.rb').read_bytes(),data=fixture)})
 results.append({'case':'hardware-renderer','runtime':run(exe,dll,out/'renderer','',(ROOT/'tests/runtime_renderer.rb').read_bytes(),timeout=120)})
 results.append({'case':'tilemap','runtime':run(exe,dll,out/'tilemap','',(ROOT/'tests/runtime_tilemap.rb').read_bytes(),timeout=120)})
 (out/'summary.json').write_text(json.dumps({'passed':True,'scope':'Core graphics primitives/effects/definitions/quad rendering; full visuals and gameplay remain unverified','runs':results},indent=2))
 print('Graphics primitives, effect timelines, 89 stock definitions, GPU pixels/queries and 40Hz counter: PASS')

if __name__=='__main__':main()
