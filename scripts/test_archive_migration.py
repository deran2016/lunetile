"""Migrate pinned stock scripts from an encrypted project without rewriting its archive."""
import argparse,json,shutil,sys
from pathlib import Path
from migrate_project import migrate
from rxdata import read
from test_runtime import ROOT,run,sha,ORIGINAL_EXE,ORIGINAL_DLL
sys.path.insert(0,str(ROOT/'tests'))
from rgssad_fixture import pack

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);ap.add_argument('original_dll',type=Path)
 ap.add_argument('replacement_dll',type=Path);ap.add_argument('ruby',type=Path);ap.add_argument('output',type=Path)
 a=ap.parse_args();out=a.output.resolve();source=out/'source';source.mkdir(parents=True,exist_ok=False)
 assert sha(a.project/'Game.exe')==ORIGINAL_EXE and sha(a.original_dll)==ORIGINAL_DLL
 shutil.copy2(a.project/'Game.exe',source/'Game.exe');shutil.copy2(a.original_dll,source/'RGSS104E.dll')
 entries=[(('Data\\'+path.name).encode(),path.read_bytes()) for path in sorted((a.project/'Data').glob('*.rxdata'))]
 blob=pack(entries);(source/'Game.rgssad').write_bytes(blob)
 (source/'Game.ini').write_text('[Game]\nLibrary=RGSS104E.dll\nScripts=Data\\Scripts.rxdata\nTitle=Archive migration\nRTP1=\nRTP2=\nRTP3=\n')
 manifest=migrate(source,out/'converted',a.replacement_dll,a.ruby)
 assert manifest['source_archive'] and manifest['result_scripts_path']=='Data/Scripts-RGSSXP.rxdata'
 assert (out/'converted/Game.rgssad').read_bytes()==blob and (source/'Game.rgssad').read_bytes()==blob
 old=read((a.project/'Data/Scripts.rxdata').read_bytes());new=read((out/'converted'/manifest['result_scripts_path']).read_bytes())
 assert [(e.id,e.name) for e in old]==[(e.id,e.name) for e in new]
 changed={'Game_Battler 1','Game_Actor','Game_Map','Window_SaveFile','Scene_Title','Scene_File','Scene_Save','Scene_Load'}
 assert {entry['name'] for entry in manifest['scripts'] if entry['changes']}==changed
 assert all(before.raw==after.raw for before,after in zip(old,new) if before.name.decode() not in changed)
 # Driver executes in a separate copy, leaving the migrated game's INI and scripts intact.
 fixture=out/'converted-driver-data';fixture.mkdir()
 shutil.copy2(out/'converted'/manifest['result_scripts_path'],fixture/'Scripts-RGSSXP.rxdata')
 names=[path.stem for path in sorted((a.project/'Data').glob('*.rxdata')) if path.stem!='Scripts']
 ruby_source=("raise 'converted script missing' unless load_data('Data/Scripts-RGSSXP.rxdata').size == 90\n"+
  '%w['+' '.join(names)+"].each { |name| load_data('Data/' + name + '.rxdata') }\n"+
  "File.write('runtime-complete.txt', 'archive-migration,false,false'); sleep 0.5\n").encode()
 result=run((source/'Game.exe').resolve(),a.replacement_dll.resolve(),out/'driver','',ruby_source,data=fixture,archive=blob,script_path='Scripts.rxdata')
 (out/'comparison.json').write_text(json.dumps({'passed':True,'archive_preserved':True,'converted_script_count':len(new),'archived_data_files_loaded':len(names),'runtime':result},indent=2))
 print('Encrypted stock project migration + preserved archive + native data/converted-script lookup PASS')

if __name__=='__main__':main()
