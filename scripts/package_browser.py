"""Package isolated XP/VXA browser demos after matching native/performance verification."""
import argparse,hashlib,json,shutil,zipfile,zlib
from pathlib import Path
from inspect_runtime import inspect
from package_template_vxa import archive
from rxdata import integer,string,read

ROOT=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def demo_scripts(source):
 entry=b'['+integer(3)+b'i'+integer(1)+string(b'Lunetile browser demo')+string(zlib.compress(source))
 result=b'\x04\x08['+integer(1)+entry
 assert read(result)[0].source()==source
 return result

def package(runtime,verification,output):
 runtime,verification,output=[Path(p).resolve() for p in (runtime,verification,output)]
 if output.exists():raise ValueError('Output already exists; refusing to overwrite')
 for source in [runtime,ROOT/'template-xp',ROOT/'template-vxa']:
  if output.is_relative_to(source) or source.is_relative_to(output):raise ValueError('Separate output directory required')
 report=json.loads(verification.read_text(encoding='utf-8'))
 if 'validation_schema' in report:
  from runtime_validation import require_report
  require_report(report,runtime,purpose='package')
 if report.get('passed') is not True or report.get('performance',{}).get('passed') is not True:raise ValueError('Passed runtime and performance verification required')
 artifacts={}
 for engine,name in [('xp','Lunetile.dll'),('vxa','LunetileVXA.dll')]:
  artifact=inspect(runtime/name,engine=engine)
  if artifact['sha256']!=report['artifacts'][engine]['sha256']:raise ValueError('Runtime differs from verified DLL')
  artifacts[engine]=artifact
 output.mkdir(parents=True)
 source=(ROOT/'tests/runtime_browser_demo.rb').read_bytes();script=demo_scripts(source)
 diagnostics=output/'diagnostics';diagnostics.mkdir()
 (diagnostics/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 shutil.copy2(ROOT/'docs/BROWSER.md',diagnostics/'BROWSER.md')
 hashes={}
 for engine,name in [('xp','Lunetile.dll'),('vxa','LunetileVXA.dll')]:
  project=output/engine;project.mkdir()
  shutil.copy2(ROOT/f'template-{engine}/Game.exe',project/'Game.exe');shutil.copy2(runtime/name,project/name)
  ext='rxdata' if engine=='xp' else 'rvdata2'
  (project/f'Scripts.{ext}').write_bytes(script)
  (project/'Game.ini').write_text(f'[Game]\nLibrary={name}\nScripts=Scripts.{ext}\nTitle=Lunetile browser demo ({engine})\nRTP=\nRTP1=\nRTP2=\nRTP3=\n[Lunetile]\nWidth=1280\nHeight=720\nTimingProfile=stock120\nRenderRate=60\n',encoding='utf-8')
  (project/'demo.rb').write_bytes(source)
  shutil.copytree(ROOT/'tests/fixtures/browser',project/'Web')
  shutil.copy2(ROOT/'LICENSE',project/'LICENSE');shutil.copytree(ROOT/'licenses',project/'licenses')
  (project/'README.txt').write_text(
   'Lunetile browser demo - '+engine+'\n\n'
   'ZIP을 새 폴더에 풀고 Game.exe를 실행하세요. 인터넷 연결과 RTP 없이 로컬 HTML을 표시합니다.\n'
   '필수: Windows 11 x64, Visual C++ x86 런타임, Microsoft Edge WebView2 Evergreen Runtime. 자동 설치하지 않습니다.\n'
   'WebView2가 없으면 게임은 계속 실행하며 설치 후 예제를 다시 실행하세요.\n'
   '브라우저 우측 상단 × 또는 포커스 중 Esc로 닫습니다. Enter/Z로 다시 열고 패널 바깥을 클릭하면 게임을 조작합니다.\n'
   '방향키로 노란 상자가 움직입니다. 브라우저 입력 중에는 멈추지만 위의 진행 틱은 계속 증가합니다.\n'
   'Alt+Enter 전체 화면, F12 리셋. 기본 출력 60FPS, 로직 120Hz입니다.\n'
   'demo.rb는 설명용 원본이며 실행 소스는 Scripts.'+ext+'에 들어 있습니다. 사용법은 진단 ZIP의 BROWSER.md를 참고하세요.\n'
   '프로필은 LocalAppData/Lunetile/WebView2에 프로젝트별로 저장합니다. 프로필·쿠키·로그를 배포하지 마세요.\n'
   '이 ZIP으로 기존 게임의 데이터나 저장을 덮어쓰지 마세요. 원본 RGSS DLL과 브라우저 Runtime은 포함하지 않습니다.\n'
   'DLL SHA256: '+artifacts[engine]['sha256']+'\n',encoding='utf-8')
  files={p.relative_to(project).as_posix():sha(p) for p in sorted(project.rglob('*')) if p.is_file()}
  (diagnostics/(engine+'-files.json')).write_text(json.dumps(files,indent=2)+'\n')
  path=output/f'lunetile-browser-{engine}-demo.zip';archive(project,path);hashes[path.name]=sha(path)
 (output/'SHA256SUMS.txt').write_text(''.join(f'{v}  {k}\n' for k,v in sorted(hashes.items())),encoding='ascii')
 return hashes

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ('runtime','verification','output'):ap.add_argument(name,type=Path)
 a=ap.parse_args();package(a.runtime,a.verification,a.output)
