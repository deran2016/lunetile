"""Check exact owned helper migration, retaining IDs/order and rejecting an altered Main."""
import argparse,json,shutil,zlib
from pathlib import Path
from migrate_project import ROOT,migrate,MigrationError,sha
from rxdata import Entry,read,write

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('ruby',type=Path);ap.add_argument('output',type=Path)
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 entries=read((a.project/'Data/Scripts.rxdata').read_bytes());original=entries[-1].source();legacy=json.loads((ROOT/'src/runtime/legacy_pacing.json').read_text())
 wrapped=original.replace(b'  # Prepare for transition',legacy['start_line'].encode()+b'  # Prepare for transition',1)
 position=wrapped.rfind(b'end');wrapped=wrapped[:position]+legacy['detach_block'].encode()+wrapped[position:]
 results=[]
 for name,separate,hooks,changed in [('inline',False,True,9),('separate',True,True,10),('unused-separate',True,False,9)]:
  source=out/(name+'-source');source.mkdir();shutil.copy2(a.project/'Game.exe',source/'Game.exe');shutil.copytree(a.project/'Data',source/'Data')
  selected=list(entries);patches={}
  if separate:
   selected.insert(len(selected)-1,Entry(0x1357246,b'RGSSNativePacing',zlib.compress(legacy['bootstrap_sources'][1].encode()),b''))
   patches[len(selected)-2]=selected[-2].source()
  if hooks:patches[len(selected)-1]=wrapped if separate else legacy['bootstrap_sources'][0].encode()+wrapped
  path=source/'Data/Scripts.rxdata';path.write_bytes(write(selected,patches));before=sha(path.read_bytes())
  (source/'RGSSFramePacing.dll').write_bytes(b'Owned helper removal fixture; never executed')
  target=out/name;manifest=migrate(source,target,a.dll,a.ruby)
  after=read((target/'Data/Scripts.rxdata').read_bytes());before_entries=read(path.read_bytes())
  assert [(e.id,e.name) for e in before_entries]==[(e.id,e.name) for e in after]
  indices={item['index'] for item in manifest['scripts'] if item['changes']}
  assert len(indices)==changed
  assert all(e.raw==after[i].raw for i,e in enumerate(before_entries) if i not in indices)
  assert after[-1].source().replace(b'\r\n',b'\n')==original.replace(b'\r\n',b'\n')
  assert not (target/'RGSSFramePacing.dll').exists() and (source/'RGSSFramePacing.dll').exists()
  assert sha(path.read_bytes())==before
  assert not any(b'RGSSNativePacing.start' in e.source() or b'RGSSNativePacing::Detach.call' in e.source() for e in after)
  results.append({'case':name,'scripts':len(after),'changed':len(indices),'preserved_raw':len(after)-len(indices),'source_preserved':True,'helper_removed':True})
 for name,code,extra in [('custom-main',legacy['bootstrap_sources'][0].encode()+wrapped+b'puts :user_code\n',False),('modified-bootstrap',legacy['bootstrap_sources'][0].replace('Attach.call==1','Attach.call==0').encode()+wrapped,False),('missing-bootstrap',wrapped,False),('unknown-extra',original,True)]:
  source=out/(name+'-source');source.mkdir();shutil.copy2(a.project/'Game.exe',source/'Game.exe');shutil.copytree(a.project/'Data',source/'Data')
  selected=list(entries);patches={len(entries)-1:code}
  if extra:
   selected.insert(len(selected)-1,Entry(4,b'Unknown',zlib.compress(b'puts :plugin'),b''));patches={len(selected)-2:b'puts :plugin'}
  path=source/'Data/Scripts.rxdata';path.write_bytes(write(selected,patches));before=sha(path.read_bytes());target=out/name
  try:migrate(source,target,a.dll,a.ruby)
  except MigrationError as error:
   assert 'Script ' in str(error) and not target.exists()
  else:raise AssertionError('Unreviewed source accepted: '+name)
  assert sha(path.read_bytes())==before
  results.append({'case':name,'rejected':True,'source_preserved':True})
 (out/'summary.json').write_text(json.dumps({'passed':True,'dll_sha256':sha(a.dll.read_bytes()),'scope':'Exact owned helper removal and strict migration; runtime boot tested separately','cases':results},indent=2)+'\n')
 print('Exact inline/separate helper migration, IDs/order/raw bytes, helper exclusion and unknown-code rejection PASS')

if __name__=='__main__':main()
