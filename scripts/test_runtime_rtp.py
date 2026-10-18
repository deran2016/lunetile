"""Read the existing Standard RTP registration; never install, copy or modify the RTP."""
import argparse,json,shutil,struct,subprocess,time,winreg,zlib
from pathlib import Path
import psutil
from test_runtime import ROOT,ORIGINAL_EXE,ORIGINAL_DLL,sha,scripts
from test_runtime_graphics import records

def png():
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',2,2,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes([17,31,47])*2)*2))+chunk(b'IEND',b'')

def run_case(exe,dll,out,rtp):
 out.mkdir();shutil.copy2(exe,out/'Game.exe');shutil.copy2(dll,out/'RGSS104E.dll')
 (out/'Graphics/Titles').mkdir(parents=True)
 (out/'override.png').write_bytes(png());(out/'rtp-root.txt').write_text(str(rtp),encoding='utf-8')
 (out/'Scripts.rxdata').write_bytes(scripts((ROOT/'tests/rgss_rtp_reference.rb').read_bytes()))
 (out/'Game.ini').write_text('[Game]\nLibrary=RGSS104E.dll\nScripts=Scripts.rxdata\nTitle=RGSS registered RTP lookup\nRTP1=Standard\nRTP2=\nRTP3=\n')
 process=subprocess.Popen([str(out/'Game.exe')],cwd=out);began=time.monotonic();images={}
 print('Registered RTP probe PID='+str(process.pid)+' '+str(out),flush=True)
 try:
  while process.poll() is None:
   if time.monotonic()-began>45:raise TimeoutError('Registered RTP probe did not exit')
   if sha(dll) not in images.values() and time.monotonic()-began>.3:
    try:images.update({item.path:sha(Path(item.path)) for item in psutil.Process(process.pid).memory_maps() if Path(item.path).suffix.lower() in ('.exe','.dll') and Path(item.path).is_file()})
    except psutil.NoSuchProcess:pass
   time.sleep(.05)
 finally:
  if process.poll() is None:process.terminate();process.wait()
  (out/'modules.json').write_text(json.dumps(images,indent=2))
  (out/'process-result.json').write_text(json.dumps({'exit_code':process.returncode,'dll_sha256':sha(dll)},indent=2))
 assert process.returncode==0 and (out/'runtime-complete.txt').exists()
 expected=sha(dll);assert expected in images.values()
 if expected!=ORIGINAL_DLL:assert ORIGINAL_DLL not in images.values()
 assert not any(Path(name).name.lower()=='rgssframepacing.dll' for name in images)
 return records(out/'types-reference.txt')

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('exe',type=Path);ap.add_argument('original',type=Path);ap.add_argument('replacement',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
 exe,old,new=[p.resolve() for p in (a.exe,a.original,a.replacement)]
 assert sha(exe)==ORIGINAL_EXE and sha(old)==ORIGINAL_DLL and sha(new)!=ORIGINAL_DLL
 with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Enterbrain\RGSS\RTP',0,winreg.KEY_READ|winreg.KEY_WOW64_32KEY) as key:
  value,kind=winreg.QueryValueEx(key,'Standard')
 if kind!=winreg.REG_SZ or not Path(value).is_dir():raise ValueError('An existing Standard RTP installation is required; no registry changes will be made')
 rtp=Path(value);assets=[rtp/name for name in ('Graphics/Titles/001-Title01.jpg','Graphics/Windowskins/001-Blue01.png','Audio/BGM/001-Battle01.mid')]
 before={str(p):sha(p) for p in (exe,old,new,*assets)}
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 original=run_case(exe,old,out/'original',rtp);replacement=run_case(exe,new,out/'replacement',rtp)
 assert set(original)==set(replacement)=={'rtp_title','rtp_skin','project_priority','rtp_audio_loaded'}
 # JPEG decode rounding is a separate contract from registered-path lookup.
 assert all(original[key]==replacement[key] for key in ('rtp_skin','project_priority','rtp_audio_loaded'))
 assert original['rtp_title'][:2]==replacement['rtp_title'][:2]==[640,480]
 jpeg_error=max(abs(x-y) for a,b in zip(original['rtp_title'][2],replacement['rtp_title'][2]) for x,y in zip(a,b))
 assert jpeg_error<=2,(original['rtp_title'],replacement['rtp_title'])
 with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Enterbrain\RGSS\RTP',0,winreg.KEY_READ|winreg.KEY_WOW64_32KEY) as key:assert winreg.QueryValueEx(key,'Standard')==(value,kind)
 assert before=={str(p):sha(p) for p in (exe,old,new,*assets)}
 report={'passed':True,'dll_sha256':sha(new),'original_sha256':sha(old),'exact_matching_records':sum(original[k]==replacement[k] for k in original),'jpeg_sample_max_channel_error':jpeg_error,'jpeg_sample_tolerance':2,'original_records':original,'records':replacement,'source_sha256':sha(ROOT/'tests/rgss_rtp_reference.rb'),'rtp_asset_hashes':{p.relative_to(rtp).as_posix():sha(p) for p in assets},'registration_and_inputs_preserved':True,'scope':'Existing HKLM 32-bit Standard RTP registration; no RTP assets copied into projects, no registry writes. Extensionless title/skin lookup, project override and MIDI file lookup/progression. Three JPEG samples allow two decoder rounding levels, PNG exact; not full image identity, acoustic fidelity or all RTP registrations/locales.'}
 (out/'summary.json').write_text(json.dumps(report,indent=2));print('Original/replacement registered RTP lookup, project priority and unchanged registration: PASS')

if __name__=='__main__':main()
