"""Run the original launcher with only the independently built replacement DLL."""
import argparse,ast,hashlib,json,shutil,subprocess,time,zlib
from pathlib import Path
import psutil

ROOT=Path(__file__).resolve().parents[1]
ORIGINAL_EXE='0ed9b5139edb0ad0f0f4b5b88dd0265ddbf56d36d6f173d6a22f3b23e8212e22'
ORIGINAL_DLL='7b6acb5e2c245b8cfda77fced2cc0e94108384cd1b9ffc8510e7304fcb9feb6c'
MODULE_HASHES={}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def integer(n):
 if n==0:return b'i\0'
 if 0<n<123:return b'i'+bytes([n+5])
 raw=n.to_bytes((n.bit_length()+7)//8,'little')
 return b'i'+bytes([len(raw)])+raw

def string(data):return b'"'+integer(len(data))[1:]+data

def scripts(source):
 return b'\x04\x08['+integer(1)[1:]+b'['+integer(3)[1:]+integer(1)+string(b'Runtime smoke')+string(zlib.compress(source))

def run(exe,dll,out,mode,source,expect_error=False,data=None,import_save=None,archive=None,script_path=None,data_encoding=None,timeout=20,screen_size=None):
 if data_encoding not in (None,'UTF-8','CP949','CP932'):raise ValueError('Unsupported test data encoding')
 if data_encoding:source=("raise 'Configured project encoding was not read' unless RGSSXP::DATA_ENCODING == "+repr(data_encoding)+"\n").encode()+source
 out.mkdir(parents=True,exist_ok=False)
 shutil.copy2(exe,out/'Game.exe');shutil.copy2(dll,out/'RGSS104E.dll')
 runtime_hash=sha(out/'RGSS104E.dll')
 if data:shutil.copytree(data,out/'Data',ignore=shutil.ignore_patterns('Scripts.rxdata'))
 if import_save:
  (out/'Saves/Import').mkdir(parents=True)
  shutil.copy2(import_save,out/'Saves/Import/Save1.rxdata')
 (out/'Scripts.rxdata').write_bytes(scripts(source))
 if script_path is None:script_path='Data/Scripts.rxdata' if archive else 'Scripts.rxdata'
 if archive:(out/'Game.rgssad').write_bytes(archive)
 ini=f'[Game]\nLibrary=RGSS104E.dll\nScripts={script_path}\nTitle=RGSSXP Runtime Test\nRTP1=\nRTP2=\nRTP3=\n'
 if screen_size:ini+='[Lunetile]\nWidth='+str(screen_size[0])+'\nHeight='+str(screen_size[1])+'\n'
 if data_encoding:ini+='[RGSSXP]\nDataEncoding='+data_encoding+'\n'
 (out/'Game.ini').write_text(ini)
 p=subprocess.Popen([str(out/'Game.exe')]+([mode] if mode else []),cwd=out)
 if timeout>20:print(f'Foreground rendering case PID={p.pid} path={out}',flush=True)
 modules={};all_modules={}
 try:
  deadline=time.monotonic()+timeout
  while p.poll() is None:
   if time.monotonic()>deadline:raise TimeoutError('Runtime did not terminate')
   try:
    for entry in psutil.Process(p.pid).memory_maps():
     path=Path(entry.path)
     if path.suffix.lower() in ('.dll','.exe') and path.is_file():
      signature=(str(path),path.stat().st_mtime_ns,path.stat().st_size)
      if signature not in MODULE_HASHES:MODULE_HASHES[signature]=sha(path)
      all_modules[str(path)]=MODULE_HASHES[signature]
     if path.name.lower() in ('rgss104e.dll','rgssframepacing.dll'):
      modules[str(path)]=sha(path)
   except psutil.NoSuchProcess:pass
   time.sleep(.05)
 finally:
  if p.poll() is None:p.terminate();p.wait()
 result={'pid':p.pid,'exit_code':p.returncode,'modules':modules,'all_image_hashes':all_modules,'runtime_sha256':runtime_hash,'complete':(out/'runtime-complete.txt').read_text() if (out/'runtime-complete.txt').exists() else None,'log':(out/'rgssxp.log').read_text(encoding='utf-8',errors='replace') if (out/'rgssxp.log').exists() else ''}
 (out/'result.json').write_text(json.dumps(result,indent=2))
 assert sha(out/'RGSS104E.dll')==runtime_hash
 assert modules and all(value==runtime_hash and value!=ORIGINAL_DLL for value in modules.values()),result
 assert ORIGINAL_DLL not in all_modules.values(),'Original RGSS found under a different filename'
 assert not any(Path(name).name.lower()=='rgssframepacing.dll' for name in modules),result
 assert 'Ruby finalized' in result['log'],result
 if expect_error:
  assert p.returncode!=0 and 'ZeroDivisionError' in result['log'],result
 else:
  assert p.returncode==0 and result['complete'],result
  flags={'':'false,false','debug':'true,false','btest':'true,true'}[mode]
  assert result['complete'].endswith(flags),result
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('output',type=Path)
 args=ap.parse_args();exe,dll,out=args.exe.resolve(),args.dll.resolve(),args.output.resolve()
 assert sha(exe)==ORIGINAL_EXE
 assert sha(dll)!=ORIGINAL_DLL
 source=(ROOT/'tests/runtime_smoke.rb').read_bytes()
 reports=[]
 for mode in ('','debug','btest'):
  reports.append(run(exe,dll,out/(mode or 'normal'),mode,source))
  assert (out/(mode or 'normal')/'runtime-finalized.txt').read_text()=='at_exit completed'
 type_source=(ROOT/'tests/rgss_types_reference.rb').read_bytes()+(ROOT/'tests/runtime_types.rb').read_bytes()+source
 reports.append(run(exe,dll,out/'types','',type_source))
 reports.append(run(exe,dll,out/'saves','',(ROOT/'tests/runtime_saves.rb').read_bytes()+source))
 skipped=[]
 try:str(out/'한글-경로').encode('mbcs',errors='strict')
 except UnicodeEncodeError:
  skipped.append({'case':'Korean project path','reason':'Original ANSI launcher cannot represent this path in the system code page'})
 else:reports.append(run(exe,dll,out/'한글-경로','',(ROOT/'tests/runtime_saves.rb').read_bytes()+source))
 reports.append(run(exe,dll,out/'wide-config','',b"raise 'INI resolution ignored' unless [Graphics.width,Graphics.height]==[1280,720]\nGraphics.update\nFile.write('runtime-complete.txt','config,false,false')",screen_size=(1280,720),timeout=40))
 reports.append(run(exe,dll,out/'resolution','',(ROOT/'tests/runtime_resolution.rb').read_bytes(),timeout=40))
 reports.append(run(exe,dll,out/'input-errors','',(ROOT/'tests/runtime_input_errors.rb').read_bytes()))
 for encoding in ('UTF-8','CP949','CP932'):
  reports.append(run(exe,dll,out/('text-'+encoding),'',(ROOT/'tests/runtime_text.rb').read_bytes()+source,data_encoding=encoding))
 reports.append(run(exe,dll,out/'win32','',(ROOT/'tests/rgss_win32_reference.rb').read_bytes()+(ROOT/'tests/runtime_win32.rb').read_bytes()))
 assert (out/'win32/types-reference.txt').read_text()==(ROOT/'tests/runtime_win32_expected.txt').read_text()
 records={}
 for line in (out/'types/types-reference.txt').read_text().splitlines():
  name,value=line.split('\t',1)
  records[name]=ast.literal_eval(value.replace('nil','None').replace('false','False').replace('true','True'))
 expected=json.loads((ROOT/'tests/runtime_types_expected.json').read_text())
 assert records==expected,{'expected':expected,'actual':records}
 reports.append(run(exe,dll,out/'ruby-error','',b'sleep 0.25; 1/0',True))
 reports.append(run(exe,dll,out/'ruby-exit','',b"at_exit { File.write('runtime-complete.txt','exit,false,false') }; sleep 0.25; exit"))
 (out/'summary.json').write_text(json.dumps(reports,indent=2))
 (out/'skipped.json').write_text(json.dumps(skipped,indent=2)+'\n')
 print('Original launcher + independent Ruby 4 x86 DLL: normal/debug/btest/types/saves/error PASS')

if __name__=='__main__':main()
