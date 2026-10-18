"""Convert the supplied template into a playable project distribution."""
import argparse,hashlib,json,shutil,tempfile
from pathlib import Path
from migrate_project import migrate

ASSETS={'Data':{'.rxdata'},'Graphics':{'.png','.jpg','.jpeg','.bmp'},'Audio':{'.ogg','.wav','.mp3','.wma','.mid','.midi'}}

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def package(source,runtime,output):
 source,runtime,output=[p.resolve() for p in (source,runtime,output)]
 if output.exists():raise ValueError('Output already exists; refusing to overwrite')
 if output.is_relative_to(source) or source.is_relative_to(output):raise ValueError('Source and output must be separate')
 report=json.loads((runtime/'verification.json').read_text(encoding='utf-8'))
 if report.get('passed') is not True or report.get('runtime_sha256')!=digest(runtime/'RGSS104E.dll'):
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
  migrate(clean,converted,runtime/'RGSS104E.dll',runtime/'rgssxp-ruby.exe',data_encoding='UTF-8')
  game=staging/'game';game.mkdir()
  for name in ('Game.exe','Game.ini','Game.rxproj','RGSS104E.dll'):
   shutil.copy2(converted/name,game/name)
  for folder in ASSETS:
   if (converted/folder).is_dir():shutil.copytree(converted/folder,game/folder)
   else:(game/folder).mkdir()
  (game/'migration').mkdir()
  shutil.copy2(converted/'migration/manifest.json',game/'migration/manifest.json')
  for name in ('LICENSE','artifact.json','verification.json','ruby.lock.json','dependencies.lock.json','ruby-msvc32-size-fetch-add.patch'):
   shutil.copy2(runtime/name,game/name)
  for folder in ('licenses','docs'):shutil.copytree(runtime/folder,game/folder)
  (game/'README.txt').write_text(
   'Lunetile - converted template project\n\n'
   '실행: 이 폴더를 풀고 Game.exe를 실행하세요. Python이나 별도 변환은 필요하지 않습니다.\n'
   '필수: Windows 11 x64, Microsoft Visual C++ x86 런타임, RPG Maker XP Standard RTP.\n'
   '원본 template은 RTP 리소스를 사용합니다. RTP는 이 ZIP에 포함하지 않습니다.\n'
   '새 저장: Saves/RGSSXP. 원본 프로젝트나 기존 세이브를 덮어쓰지 마세요.\n'
   'Game.rxproj와 Data는 변환된 프로젝트이며 기본 XP 스크립트를 덮어쓰면 호환 처리가 사라질 수 있습니다.\n\n'
   'Experimental build. See verification.json for this DLL\'s CI checks.\n'
   'Template conversion is checked; full gameplay/rendering/audio acceptance is not certified.\n'
   'Lunetile code: MIT. Template game files are not relicensed by the engine license.\n'
   'See licenses/ and docs/RUNTIME_THIRD_PARTY.md for dependency notices.\n',encoding='utf-8')
  if before!={p.relative_to(source).as_posix():digest(p) for p in selected}:raise ValueError('Template inputs changed during packaging')
  (game/'template-source.json').write_text(json.dumps(before,indent=2)+'\n',encoding='utf-8')
  hashes={p.relative_to(game).as_posix():digest(p) for p in sorted(game.rglob('*')) if p.is_file()}
  (game/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
  game.rename(output)
 return hashes

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('source',type=Path);parser.add_argument('runtime',type=Path);parser.add_argument('output',type=Path)
 args=parser.parse_args()
 hashes=package(args.source,args.runtime,args.output)
 print(f'Converted template package: {args.output} ({len(hashes)} verified files; Standard RTP required)')
