"""Package a verified development DLL, its source locks and third-party notices."""
import argparse,difflib,hashlib,json,shutil,subprocess
from pathlib import Path
from inspect_runtime import inspect
from patch_runtime_ruby import BEFORE,AFTER,ORIGINAL

ROOT=Path(__file__).resolve().parents[1]

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('verification',type=Path);ap.add_argument('output',type=Path)
 ap.add_argument('--dll',type=Path,default=ROOT/'build/runtime-native/bin/Release/RGSS104E.dll')
 ap.add_argument('--integration-report',type=Path,action='append',default=[])
 ap.add_argument('--performance-report',type=Path)
 ap.add_argument('--audio-report',type=Path)
 ap.add_argument('--compressed-audio-report',type=Path)
 ap.add_argument('--wma-report',type=Path)
 a=ap.parse_args();artifact=inspect(a.dll)
 report=json.loads((a.verification/'summary.json').read_text(encoding='utf-8'))
 if not report['passed'] or report['runtime_sha256']!=artifact['sha256']:raise ValueError('DLL does not match a passed verification report')
 helper=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'
 probe=subprocess.run([str(helper),'--disable-gems','-e','puts [RUBY_VERSION,[0].pack("J").bytesize,Encoding.find("CP949").name,Encoding.find("CP932").name].join("|")'],capture_output=True,text=True,timeout=15)
 if probe.returncode or probe.stdout.strip()!='4.0.7|4|CP949|Windows-31J':raise ValueError('Ruby migration helper version/architecture/encodings did not pass')
 helper_info={'file':helper.name,'sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),'ruby':'4.0.7','architecture':'x86','tested_encodings':['CP949','CP932'],'scope':'Migration/syntax/encoding tool only; not required while playing'}
 integrations=[]
 for path in a.integration_report:
  check=json.loads(path.read_text(encoding='utf-8'))
  if not check['passed'] or check['dll_sha256']!=artifact['sha256']:raise ValueError('Integration report does not match the DLL')
  integrations.append({'case':path.parent.name,'passed':True,'scope':check['scope'],'dll_sha256':check['dll_sha256'],'states':check['states']})
  if 'endurance' in check:integrations[-1]['endurance']=check['endurance']
 performance=None
 if a.performance_report:
  performance=json.loads(a.performance_report.read_text(encoding='utf-8'))
  if performance['dll_sha256']!=artifact['sha256'] or performance['pairs']<3:raise ValueError('Performance report does not match the DLL and three-pair scope')
 audio=None
 if a.audio_report:
  audio=json.loads(a.audio_report.read_text(encoding='utf-8'))
  expected={(format,pitch) for format in ('wav','mid') for pitch in (50,100,150)}
  if not audio.get('measurement_valid') or not audio.get('tone_and_envelope_gate_passed') or audio['replacement']['dll_sha256']!=artifact['sha256']:raise ValueError('Audio report does not match the DLL and passed tone/envelope gate')
  if audio['original']['dll_sha256']!='7b6acb5e2c245b8cfda77fced2cc0e94108384cd1b9ffc8510e7304fcb9feb6c' or len(audio['checks'])!=6 or {(row['format'],row['pitch']) for row in audio['checks']}!=expected or not all(row['passed'] for row in audio['checks']):raise ValueError('Audio report does not cover the original and all six tone/pitch cases')
  if any(row['format']=='mid' and row.get('first_note_not_delayed_over_100ms') is not True for row in audio['checks']):raise ValueError('Audio report must compare the first MIDI note, not only later loop envelopes')
 compressed=None
 if a.compressed_audio_report:
  compressed=json.loads(a.compressed_audio_report.read_text(encoding='utf-8'))
  expected={(format,pitch) for format in ('ogg','mp3','wma') for pitch in (50,100,150)}
  if not compressed.get('measurement_valid') or not compressed.get('tone_and_envelope_gate_passed') or compressed['replacement']['dll_sha256']!=artifact['sha256'] or compressed['original']['dll_sha256']!='7b6acb5e2c245b8cfda77fced2cc0e94108384cd1b9ffc8510e7304fcb9feb6c':raise ValueError('Compressed audio report does not identify passed original/replacement captures for this DLL')
  if len(compressed['checks'])!=9 or {(row['format'],row['pitch']) for row in compressed['checks']}!=expected or not all(row['passed'] for row in compressed['checks']):raise ValueError('Compressed audio report must cover all nine format/pitch cases')
 wma=None
 if a.wma_report:
  wma=json.loads(a.wma_report.read_text(encoding='utf-8'))
  expected={(role,pitch) for role in ('bgm','bgs','me','se') for pitch in (50,100,150)}
  if not wma.get('passed') or wma['dll_sha256']!=artifact['sha256'] or wma['replacement']['dll_sha256']!=artifact['sha256'] or wma['original']['dll_sha256']!='7b6acb5e2c245b8cfda77fced2cc0e94108384cd1b9ffc8510e7304fcb9feb6c':raise ValueError('WMA report does not identify passed original/replacement captures for this DLL')
  if len(wma['checks'])!=12 or {(row['role'],row['pitch']) for row in wma['checks']}!=expected or not all(row['passed'] for row in wma['checks']):raise ValueError('WMA report must cover all twelve role/pitch cases')
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 shutil.copy2(a.dll,out/'RGSS104E.dll');shutil.copy2(ROOT/'LICENSE',out/'LICENSE')
 shutil.copy2(helper,out/helper.name)
 (out/'ruby-helper.json').write_text(json.dumps(helper_info,indent=2)+'\n')
 scripts=out/'scripts';scripts.mkdir()
 for name in ('migrate_project.py','rxdata.py','inspect_runtime.py','rgssad.py','check_project_data.rb'):shutil.copy2(ROOT/'scripts'/name,scripts/name)
 resources=out/'src/runtime';resources.mkdir(parents=True)
 for name in ('stock_scripts.json','rpg_schema.json','text.rb','abi.json','legacy_pacing.json'):shutil.copy2(ROOT/'src/runtime'/name,resources/name)
 shutil.copytree(ROOT/'docs',out/'docs')
 for name in ('ruby.lock.json','dependencies.lock.json','abi.json','exports.json'):shutil.copy2(ROOT/'src/runtime'/name,out/name)
 gate=json.loads((ROOT/'build/runtime-ruby-x86/patched-4.0.7/gate.json').read_text(encoding='utf-8-sig'))
 ruby=Path(gate['source_directory']);zlib=ROOT/'build/runtime-deps/zlib-1.3.2'
 notices=out/'licenses';notices.mkdir()
 for name in ('COPYING','COPYING.ja','BSDL','LEGAL'):shutil.copy2(ruby/name,notices/('Ruby-'+name))
 shutil.copy2(zlib/'LICENSE',notices/'zlib-LICENSE')
 for name,folder in [('ogg','libogg-1.3.6'),('vorbis','libvorbis-1.3.7')]:
  shutil.copy2(ROOT/'build/runtime-deps'/folder/'COPYING',notices/(name+'-COPYING'))
 patched=(ruby/'include/ruby/atomic.h').read_bytes()
 pristine=patched.replace(AFTER,BEFORE)
 if hashlib.sha256(pristine).hexdigest()!=ORIGINAL:raise ValueError('Ruby port patch does not match verified source')
 patch=''.join(difflib.unified_diff(pristine.decode().splitlines(True),patched.decode().splitlines(True),fromfile='a/include/ruby/atomic.h',tofile='b/include/ruby/atomic.h'))
 (out/'ruby-msvc32-size-fetch-add.patch').write_text(patch,encoding='utf-8')
 (out/'artifact.json').write_text(json.dumps(artifact,indent=2)+'\n')
 # Do not bundle raw oracle graphs, proprietary scripts, assets or imported saves.
 (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
 (out/'integration.json').write_text(json.dumps(integrations,indent=2)+'\n')
 if performance:(out/'performance.json').write_text(json.dumps(performance,indent=2)+'\n')
 if audio:(out/'audio-validation.json').write_text(json.dumps(audio,indent=2)+'\n')
 if compressed:(out/'compressed-audio-validation.json').write_text(json.dumps(compressed,indent=2)+'\n')
 if wma:(out/'wma-audio-validation.json').write_text(json.dumps(wma,indent=2)+'\n')
 (out/'README.txt').write_text('Lunetile development build: Ruby 4.0.7 x86\n\nNOT A CERTIFIED GAME ENGINE RELEASE.\nImplemented for reviewed stock XP projects; validation scope is defined by the included reports. This is not universal game compatibility certification.\nDo not replace your installed RGSS104E.dll. Use a separate project copy.\nNo original RGSS DLL or frame-pacing helper is required by this DLL.\nRequires Windows 11 x64 and the Microsoft Visual C++ x86 runtime.\nRead docs/history/RUNTIME_STATUS.md for exact implemented and unimplemented scope.\n\nMigration (Python 3.12+; output must not exist):\n  python scripts/migrate_project.py ORIGINAL_PROJECT NEW_PROJECT\nFor non-ASCII data/INI, specify the actual --data-encoding and --ini-encoding; see docs/history/RUNTIME_TEXT.md.\nrgssxp-ruby.exe is the syntax/encoding helper; it is not required while playing.\n\nRuby, zlib, libogg and libvorbis sources/hashes and the Ruby porting patch are documented in the lock files.\nOwn code is MIT; library notices are in licenses/.\n',encoding='utf-8')
 files={path.relative_to(out).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(out.rglob('*')) if path.is_file()}
 (out/'SHA256SUMS.json').write_text(json.dumps(files,indent=2)+'\n')
 print('Development package: '+str(out))

if __name__=='__main__':main()
