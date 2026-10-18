"""Compare stock integer ID-table enumeration with RGSS1, including rehash and import order."""
import argparse,json,subprocess,sys
from pathlib import Path
from test_runtime import ROOT,run
from test_runtime_graphics import records
from migrate_project import transform
from rxdata import read

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);ap.add_argument('original_dll',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('output',type=Path)
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 probe=ROOT/'tests/rgss_integer_hash_reference.rb'
 command=[sys.executable,str(ROOT/'scripts/probe_original_types.py'),str((a.project/'Game.exe').resolve()),str(a.original_dll.resolve()),str(out/'original'),'--probe',str(probe)]
 with (out/'original.log').open('w') as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
 source=probe.read_bytes()+b'\n'+(ROOT/'tests/runtime_integer_map.rb').read_bytes()
 result=run((a.project/'Game.exe').resolve(),a.dll.resolve(),out/'replacement','',source)
 expected=records(out/'original/types-reference.txt');actual=records(out/'replacement/types-reference.txt')
 differences=[name for name in expected if actual.get(name)!=expected[name]]
 assert not differences,{'different_cases':differences}
 entries=read((a.project/'Data/Scripts.rxdata').read_bytes());replacements,_=transform(entries)
 chosen=[(i,e) for i,e in enumerate(entries) if e.name.startswith((b'Game_',b'Interpreter '))]
 original_source=b'\n'.join(e.source() for _,e in chosen)+b'\n'+(ROOT/'tests/rgss_event_order_reference.rb').read_bytes()
 own_probe=out/'event-probe.rb';own_probe.write_bytes(original_source)
 command=[sys.executable,str(ROOT/'scripts/probe_original_types.py'),str((a.project/'Game.exe').resolve()),str(a.original_dll.resolve()),str(out/'events-original'),'--probe',str(own_probe),'--data',str((a.project/'Data').resolve())]
 with (out/'events-original.log').open('w') as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
 converted_source=b'\n'.join(replacements.get(i,e.source()) for i,e in chosen)+b'\n'+(ROOT/'tests/rgss_event_order_reference.rb').read_bytes()+b"\nFile.write('runtime-complete.txt','event-order,false,false'); sleep 0.5\n"
 events_run=run((a.project/'Game.exe').resolve(),a.dll.resolve(),out/'events-replacement','',converted_source,data=out/'events-original/Data')
 old=records(out/'events-original/types-reference.txt');new=records(out/'events-replacement/types-reference.txt')
 assert old==new,{'different_event_cases':[key for key in old if old[key]!=new.get(key)]}
 (out/'summary.json').write_text(json.dumps({'passed':True,'matching_order_records':len(expected),'matching_event_records':len(old),'scope':'Stock ID ordering, overlapping decision/contact events, parallel execution and original save import; not arbitrary Ruby Hash semantics','runtime':result,'event_runtime':events_run},indent=2))
 print('Stock integer ID order: '+str(len(expected))+' original comparisons, new-save aliases/capacity/frozen/error guards PASS')

if __name__=='__main__':main()
