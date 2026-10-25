"""Convert the supplied template into a playable project distribution."""
import argparse,hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
from migrate_project import migrate

ASSETS={'Data':{'.rxdata'},'Graphics':{'.png','.jpg','.jpeg','.bmp'},'Audio':{'.ogg','.wav','.mp3','.wma','.mid','.midi'}}
ROOT=Path(__file__).resolve().parents[1]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def expand_map(project,ruby,staging):
 files=('Data/Map001.rxdata','Data/System.rxdata')
 before={name:digest(project/name) for name in files}
 declarations=['module RPG; end']
 for name,fields in json.loads((ROOT/'src/runtime/rpg_schema.json').read_text()).items():
  declarations.append('class '+name+'; attr_accessor '+','.join(':'+field for field in fields)+'; end')
 helper=staging/'expand-map.rb'
 helper.write_text('\n'.join(declarations)+'\n'+(ROOT/'scripts/expand_template_map.rb').read_text(),encoding='utf-8')
 result=subprocess.run([str(ruby),'--disable-gems',str(helper),str(project)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15)
 if result.returncode:raise ValueError('Template map expansion failed: '+result.stderr)
 previous,current,x,y=json.loads(result.stdout)
 return {'map':'Data/Map001.rxdata','size_before':[20,15,3],'size_after':[40,23,3],
  'extension_tiles':[384,0,0],'start':[1,x,y],'magic_number_before':previous,'magic_number_after':current,
  'sha256_before':before,'sha256_after':{name:digest(project/name) for name in files}}

def package(source,runtime,output,diagnostics):
 source,runtime,output,diagnostics=[p.resolve() for p in (source,runtime,output,diagnostics)]
 for target in (output,diagnostics):
  if target.exists():raise ValueError('Output already exists; refusing to overwrite')
  for other in (source,runtime,diagnostics if target==output else output):
   if target.is_relative_to(other) or other.is_relative_to(target):raise ValueError('Inputs and outputs must be separate')
 report=json.loads((runtime/'verification.json').read_text(encoding='utf-8'))
 if report.get('passed') is not True or report.get('runtime_sha256')!=digest(runtime/'Lunetile.dll'):
  raise ValueError('Runtime does not match passed verification')
 selected=[source/name for name in ('Game.exe','Game.ini','Game.rxproj')]
 for folder,extensions in ASSETS.items():
  selected.extend(p for p in (source/folder).rglob('*') if p.is_file() and p.suffix.lower() in extensions)
 for p in selected:
  if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(source):raise ValueError('Invalid template input: '+str(p))
 before={p.relative_to(source).as_posix():digest(p) for p in selected}
 with tempfile.TemporaryDirectory(prefix='template-package-',dir=output.parent) as temporary:
  staging=Path(temporary);clean=staging/'source';clean.mkdir()
  for p in selected:
   target=clean/p.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
  converted=staging/'converted'
  migrate(clean,converted,runtime/'Lunetile.dll',runtime/'rgssxp-ruby.exe',data_encoding='UTF-8',widescreen=True,high_refresh=True)
  map_changes=expand_map(converted,runtime/'rgssxp-ruby.exe',staging)
  game=staging/'game';game.mkdir()
  diagnostic_files=staging/'diagnostics';diagnostic_files.mkdir()
  for name in ('Game.exe','Game.ini','Game.rxproj','Lunetile.dll'):
   shutil.copy2(converted/name,game/name)
  for folder in ASSETS:
   if (converted/folder).is_dir():shutil.copytree(converted/folder,game/folder)
   else:(game/folder).mkdir()
  (diagnostic_files/'migration').mkdir()
  shutil.copy2(converted/'migration/manifest.json',diagnostic_files/'migration/manifest.json')
  for name in ('artifact.json','verification.json','ruby.lock.json','dependencies.lock.json','ruby-msvc32-size-fetch-add.patch'):
   shutil.copy2(runtime/name,diagnostic_files/name)
  shutil.copy2(runtime/'LICENSE',game/'LICENSE')
  shutil.copytree(runtime/'licenses',game/'licenses')
  (game/'README.txt').write_text(
   'Lunetile XP - converted template project\n\n'
   '실행: 이 폴더를 풀고 Game.exe를 실행하세요. Python이나 별도 변환은 필요하지 않습니다.\n'
   '엔진: Lunetile.dll (Game.ini의 Library 설정으로 선택). 원본 RGSS DLL은 포함하지 않습니다.\n'
   '필수: Windows 11 x64, Microsoft Visual C++ x86 런타임, RPG Maker XP Standard RTP.\n'
   '원본 template-xp는 RTP 리소스를 사용합니다. RTP는 이 ZIP에 포함하지 않습니다.\n'
   '영문 Windows에서는 영문 경로에 압축을 푸세요. 기존 실행기는 시스템 ANSI 코드페이지 밖의 경로를 지원하지 않습니다.\n'
   '화면: 1280x720 와이드, 시작 맵 40x23칸. 창 크기 조절/최대화, Alt+Enter 전체 화면.\n'
   '출력: 기본 60FPS. 게임 메뉴 끝의 화면 설정에서 40/60/120FPS를 선택하고 저장할 수 있습니다. 로직은 120Hz입니다.\n'
   '고주기 저장은 버전 2입니다. 기존 저장은 읽을 수 있지만 새 저장은 이전 런타임에서 읽을 수 없습니다.\n'
   '새 저장: Saves/RGSSXP. 원본 프로젝트나 기존 세이브를 덮어쓰지 마세요.\n'
   'Game.rxproj와 Data는 변환된 프로젝트이며 기본 XP 스크립트를 덮어쓰면 호환 처리가 사라질 수 있습니다.\n\n'
   '개발용 통신 API: REST/JSON 및 TCP/TLS. 스크립트가 명시적으로 호출하기 전에는 서버에 접속하지 않습니다.\n'
   '사용법: https://github.com/deran2016/lunetile/blob/main/docs/NETWORKING.md\n\n'
   '검증 결과·변환 기록·파일 해시: 같은 Release의 lunetile-template-xp-diagnostics.zip (실행에는 불필요).\n'
   '개발 문서·소스: https://github.com/deran2016/lunetile\n'
   'Experimental build; full gameplay/rendering/audio acceptance is not certified.\n'
   'Lunetile code: MIT. Template game files are not relicensed by the engine license.\n'
   'See licenses/ for dependency notices.\n',encoding='utf-8')
  if before!={p.relative_to(source).as_posix():digest(p) for p in selected}:raise ValueError('Template inputs changed during packaging')
  (diagnostic_files/'template-source.json').write_text(json.dumps(before,indent=2)+'\n',encoding='utf-8')
  (diagnostic_files/'template-map.json').write_text(json.dumps(map_changes,indent=2)+'\n',encoding='utf-8')
  hashes={p.relative_to(game).as_posix():digest(p) for p in sorted(game.rglob('*')) if p.is_file()}
  (diagnostic_files/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
  game.rename(output)
  try:diagnostic_files.rename(diagnostics)
  except OSError:
   output.rename(game)
   raise
 return hashes

def runtime_patch_archive(project,path):
 from package_template_vxa import archive
 with tempfile.TemporaryDirectory(prefix='xp-runtime-patch-',dir=path.parent) as tmp:
  directory=Path(tmp)
  for name in ('Lunetile.dll','LICENSE'):shutil.copy2(project/name,directory/name)
  shutil.copytree(project/'licenses',directory/'licenses')
  (directory/'README.txt').write_text(
   'Lunetile XP runtime update\n\n'
   '이미 Lunetile로 변환한 프로젝트용입니다. 게임과 편집기를 종료한 뒤 Lunetile.dll만 Game.exe 옆에 교체하세요.\n'
   'Data, Saves, Game.ini, MMO 계정/프로필/스크립트/서버는 이 ZIP에 포함하지 않습니다.\n'
   '표시 객체 순회·문자 마스크 재사용·Bitmap 부분 업로드를 개선했습니다.\n'
   '모든 PC/플러그인의 120FPS를 보장하지 않습니다.\n'
   'DLL SHA256: '+digest(directory/'Lunetile.dll')+'\n',encoding='utf-8')
  archive(directory,path)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('source',type=Path);parser.add_argument('runtime',type=Path);parser.add_argument('output',type=Path);parser.add_argument('diagnostics',type=Path)
 parser.add_argument('--runtime-patch',type=Path)
 args=parser.parse_args()
 hashes=package(args.source,args.runtime,args.output,args.diagnostics)
 if args.runtime_patch:runtime_patch_archive(args.output,args.runtime_patch)
 print(f'Converted template package: {args.output} ({len(hashes)} verified files; Standard RTP required)')
