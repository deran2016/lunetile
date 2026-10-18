"""Validate explicitly selected legacy data/INI text without rewriting original data bytes."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
from test_runtime import sha,ROOT,run
from rxdata import integer,read
from migrate_project import migrate,MigrationError,transform

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('ruby',type=Path);ap.add_argument('output',type=Path)
 ap.add_argument('--original-dll',type=Path)
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);results=[]
 for encoding,text in [('CP949','한글'),('CP932','日本語')]:
  source=out/('원본-'+encoding);source.mkdir();shutil.copy2(a.project/'Game.exe',source/'Game.exe');shutil.copytree(a.project/'Data',source/'Data')
  actors=source/'Data/Actors.rxdata';raw=actors.read_bytes();before=b'"'+integer(6)+b'Aluxes'
  assert raw.count(before)==1,'Pinned stock actor-name fixture changed'
  encoded=text.encode(encoding);actors.write_bytes(raw.replace(before,b'"'+integer(len(encoded))+encoded))
  (source/'Game.ini').write_text('[Game]\nTitle='+text+'\nRTP1=\nRTP2=\nRTP3=\n',encoding=encoding)
  original_save=None
  if a.original_dll:
   entries=read((a.project/'Data/Scripts.rxdata').read_bytes());patches,_=transform(entries)
   chosen=[(i,e) for i,e in enumerate(entries) if e.name.startswith((b'Game_',b'Interpreter '))]
   probe=out/(encoding+'-save-probe.rb');probe.write_bytes(b'\n'.join(e.source() for _,e in chosen)+b'\n'+(ROOT/'tests/rgss_text_save_reference.rb').read_bytes())
   original_output=out/(encoding+'-original-save')
   with (out/(encoding+'-original-save.log')).open('w') as log:
    subprocess.run([sys.executable,str(ROOT/'scripts/probe_original_types.py'),str((source/'Game.exe').resolve()),str(a.original_dll.resolve()),str(original_output),'--probe',str(probe),'--data',str(source/'Data')],check=True,stdout=log,stderr=subprocess.STDOUT)
   original_save=original_output/'Save1.rxdata';shutil.copy2(original_save,source/'Save1.rxdata')
  original={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
  for invalid in (None,'UTF-8'):
   rejected=out/(encoding+'-rejected-'+str(invalid))
   try:migrate(source,rejected,a.dll,a.ruby,invalid,encoding)
   except MigrationError as error:
    assert 'Actors.rxdata' in str(error),str(error)
    assert not rejected.exists()
   else:raise AssertionError('Missing/wrong project encoding was accepted')
  destination=out/(encoding+'-converted')
  manifest=migrate(source,destination,a.dll,a.ruby,encoding,encoding)
  assert original=={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
  assert sha(destination/'Data/Actors.rxdata')==sha(actors),'Migration rewrote original data bytes'
  changes=manifest['data_text_changes']
  assert any(item['location']=='Actors.rxdata[1].@name' and item['source_bytes_hex']==encoded.hex() and item['utf8_bytes_hex']==text.encode().hex() for item in changes),changes
  assert manifest['ini_encoding_after']=='UTF-16LE-BOM' and manifest['data_encoding']==encoding
  case={'encoding':encoding,'string_change_count':len(changes),'originals_preserved':True,'converted_actor_bytes_preserved':True}
  if original_save:
   original_digest=sha(original_save)
   code=b'\n'.join(patches.get(i,e.source()) for i,e in chosen)+b'\n'+(ROOT/'tests/runtime_text_import.rb').read_bytes()
   native=run((source/'Game.exe').resolve(),a.dll.resolve(),out/(encoding+'-runtime'),'',code,data=destination/'Data',import_save=destination/'Saves/Import/Save1.rxdata',data_encoding=encoding)
   assert sha(original_save)==original_digest and sha(out/(encoding+'-runtime')/'Saves/Import/Save1.rxdata')==original_digest
   case['original_save_sha256']=original_digest;case['native_import_and_new_save_reload']=native
  results.append(case)
 (out/'summary.json').write_text(json.dumps({'passed':True,'scope':'CLI copy/validation/explicit in-memory conversion records; actual UI and save import tested separately','cases':results},indent=2))
 print('Explicit CP949/CP932 data and INI migration, wrong/absent encoding rejection, preserved bytes and per-field records PASS')

if __name__=='__main__':main()
