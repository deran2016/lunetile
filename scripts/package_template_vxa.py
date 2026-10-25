"""Package the reviewed VX Ace template; require matching native verification."""
import argparse,json,shutil,subprocess,tempfile,zipfile
from pathlib import Path
from migrate_project import ROOT,sha,migrate
from migrate_vxa import declarations

ASSETS={'Data':{'.rvdata2'},'Graphics':{'.png','.jpg','.jpeg','.bmp'},'Audio':{'.ogg','.wav','.mp3','.wma','.mid','.midi'},'Movies':{'.ogv'},'Fonts':{'.ttf','.otf'}}
def digest(path):return sha(path.read_bytes())

def expand_map(project,ruby,staging):
 helper=staging/'expand-vxa.rb'
 helper.write_text(declarations()+'\n'+(ROOT/'scripts/expand_vxa_map.rb').read_text(encoding='utf-8'),encoding='utf-8')
 before={p.name:digest(p) for p in (project/'Data').glob('Map*.rvdata2')}
 result=subprocess.run([str(ruby),'--disable-gems',str(helper),str(project)],capture_output=True,text=True,encoding='utf-8',timeout=30)
 if result.returncode:raise ValueError('VX Ace map expansion failed: '+result.stderr)
 map_id,x,y,nx,ny,sx,sy=json.loads(result.stdout);name=f'Map{map_id:03d}.rvdata2'
 return {'map':'Data/'+name,'size_before':[x,y,4],'size_after':[nx,ny,4],'start':[map_id,sx,sy],'sha256_before':before[name],'sha256_after':digest(project/'Data'/name)}

def package(source,runtime,output,diagnostics,*,performance=None):
 source,runtime,output,diagnostics=[Path(p).resolve() for p in (source,runtime,output,diagnostics)]
 for target in (output,diagnostics):
  if target.exists():raise ValueError('Output already exists; refusing to overwrite')
  for other in (source,runtime,diagnostics if target==output else output):
   if target.is_relative_to(other) or other.is_relative_to(target):raise ValueError('Inputs and outputs must be separate')
 dll=runtime/'LunetileVXA.dll'
 report=json.loads((runtime/'verification-vxa.json').read_text(encoding='utf-8'))
 if report.get('passed') is not True or report.get('runtime_sha256')!=digest(dll):raise ValueError('VX Ace runtime does not match passed verification')
 if performance:
  measured=json.loads(Path(performance).read_text(encoding='utf-8'))
  if measured.get('passed') is not True or measured.get('candidate_sha256')!=digest(dll):raise ValueError('Performance report does not match passed runtime')
 selected=[source/name for name in ('Game.exe','Game.ini','Game.rvproj2')]
 for folder,extensions in ASSETS.items():selected.extend(p for p in (source/folder).rglob('*') if p.is_file() and p.suffix.lower() in extensions)
 for path in selected:
  if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(source):raise ValueError('Invalid template input')
 before={p.relative_to(source).as_posix():digest(p) for p in selected}
 with tempfile.TemporaryDirectory(prefix='template-vxa-',dir=output.parent) as tmp:
  staging=Path(tmp);clean=staging/'source';clean.mkdir()
  for path in selected:
   target=clean/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
  converted=staging/'converted'
  migrate(clean,converted,dll,runtime/'rgssxp-ruby.exe',widescreen=True,high_refresh=True,engine='vxa')
  changes=expand_map(converted,runtime/'rgssxp-ruby.exe',staging)
  diagnostic=staging/'diagnostics';diagnostic.mkdir()
  (diagnostic/'migration').mkdir()
  shutil.copy2(converted/'migration/manifest.json',diagnostic/'migration/manifest.json')
  working_files=(converted/'migration').resolve()
  if not working_files.is_relative_to(staging.resolve()):raise ValueError('Migration files escaped packaging staging directory')
  shutil.rmtree(working_files)
  shutil.copy2(runtime/'verification-vxa.json',diagnostic/'verification-vxa.json')
  if performance:shutil.copy2(performance,diagnostic/'render-performance.json')
  for name in ('abi_vxa.json','ruby.lock.json','dependencies.lock.json'):
   shutil.copy2(ROOT/'src/runtime'/name,diagnostic/name)
  shutil.copy2(ROOT/'LICENSE',converted/'LICENSE');shutil.copytree(ROOT/'licenses',converted/'licenses')
  (converted/'README.txt').write_text('Lunetile VX Ace template\n\nGame.exe 실행. RPG Maker VX Ace RTP 및 Visual C++ x86 런타임 필요.\n1280x720, 120Hz 로직. 출력 40/60/120FPS.\n새 저장: Saves/LunetileVXA. RTP와 원본 RGSS301.dll은 포함하지 않습니다.\n편집기 저장으로 런타임 경로가 바뀌면 Main의 복구 코드가 LunetileVXA.dll을 선택하고 게임을 한 번 다시 시작합니다.\n전체 게임 및 사용자 스크립트 호환은 인증하지 않았습니다.\n',encoding='utf-8')
  if before!={p.relative_to(source).as_posix():digest(p) for p in selected}:raise ValueError('Template inputs changed during packaging')
  hashes={p.relative_to(converted).as_posix():digest(p) for p in sorted(converted.rglob('*')) if p.is_file()}
  for name,value in (('template-source.json',before),('template-map.json',changes),('SHA256SUMS.json',hashes)):
   (diagnostic/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
  converted.rename(output)
  try:diagnostic.rename(diagnostics)
  except OSError:
   output.rename(converted);raise
 return hashes

def archive(directory,path):
 if path.exists():raise ValueError('ZIP already exists; refusing to overwrite')
 with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED) as output:
  for item in sorted(directory.rglob('*')):
   if item.is_file():output.write(item,item.relative_to(directory).as_posix())
 with zipfile.ZipFile(path) as result:
  if result.testzip():raise ValueError('ZIP checksum validation failed')
  for item in result.namelist():
   if sha(result.read(item))!=digest(directory/item):raise ValueError('ZIP content mismatch')

def runtime_patch_archive(project,path):
 with tempfile.TemporaryDirectory(prefix='vxa-speed-fix-',dir=path.parent) as tmp:
  directory=Path(tmp)
  for name in ('LunetileVXA.dll','LICENSE'):shutil.copy2(project/name,directory/name)
  shutil.copytree(project/'licenses',directory/'licenses')
  (directory/'README.txt').write_text(
   'Lunetile VX Ace rendering and 120Hz speed fix\n\n'
   '게임과 편집기를 종료하고 변환본을 백업하세요.\n'
   'LunetileVXA.dll을 기존 Game.exe 옆에 복사하여 교체하세요.\n'
   'Data, Saves, Game.ini는 변경하지 않습니다. 전체 템플릿으로 기존 프로젝트를 덮어쓰지 마세요.\n'
   'alpha.10 이상 변환본에 적용할 수 있습니다. 이전 버전은 편집기 복구 스크립트도 적용하세요.\n'
   '타일 순회 캐시와 네이티브 D3D 인스턴스 배치로 CPU 처리와 Ruby 객체 할당을 줄였습니다.\n'
   '공용 표시 객체 순회·문자 마스크 재사용·Bitmap 부분 업로드도 개선했습니다.\n'
   '렌더링이 늦으면 출력 프레임을 건너뛰어 120Hz 게임 로직을 따라잡습니다. 실제 120FPS 출력을 보장하지 않습니다.\n'
   'DLL SHA256: '+digest(directory/'LunetileVXA.dll')+'\n',encoding='utf-8')
  archive(directory,path)

def editor_fix_archive(path):
 with tempfile.TemporaryDirectory(prefix='vxa-editor-fix-',dir=path.parent) as tmp:
  directory=Path(tmp)
  shutil.copy2(ROOT/'src/runtime/vxa_entry.rb',directory/'LunetileEditorFix.rb')
  (directory/'README.txt').write_text(
   'Lunetile VX Ace editor-save fix (existing alpha.9 projects)\n\n'
   '프로젝트를 먼저 백업하세요. DLL 복사만으로는 편집기 저장 후 오류를 막을 수 없습니다.\n'
   'VX Ace 스크립트 편집기(F11)에서 Main 바로 위에 빈 항목을 추가하고,\n'
   'LunetileEditorFix.rb 내용을 붙여 넣은 뒤 저장하세요. Game.exe 옆의 LunetileVXA.dll은 유지하세요.\n'
   '맵, 기존 스크립트와 Saves를 덮어쓰지 마세요. 이 ZIP은 자동 설치되지 않습니다.\n'
   '편집기가 원본 런타임을 선택하면 이 스크립트가 Game.ini의 Library를 복원하고 Game.exe를 한 번 재시작합니다.\n'
   '새 전체 템플릿 ZIP에는 이미 포함되어 있어 별도로 설치할 필요가 없습니다.\n',
   encoding='utf-8')
  archive(directory,path)

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ('source','runtime','output','diagnostics'):ap.add_argument(name,type=Path)
 ap.add_argument('--zip',action='store_true')
 ap.add_argument('--editor-fix',type=Path)
 ap.add_argument('--runtime-patch',type=Path)
 ap.add_argument('--performance-report',type=Path)
 args=ap.parse_args();package(args.source,args.runtime,args.output,args.diagnostics,performance=args.performance_report)
 if args.zip:
  archive(args.output,args.output.parent/'lunetile-template-vxa-windows-x86.zip')
  archive(args.diagnostics,args.diagnostics.parent/'lunetile-template-vxa-diagnostics.zip')
 if args.editor_fix:editor_fix_archive(args.editor_fix)
 if args.runtime_patch:runtime_patch_archive(args.output,args.runtime_patch)
