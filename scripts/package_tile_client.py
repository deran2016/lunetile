"""Package exact verified XP/VXA tile DLLs; never modifies templates or publishes."""
import argparse,json,shutil,hashlib,zipfile
from pathlib import Path
from inspect_runtime import inspect
from benchmark_runtime_client import tile_compare,render_accepted,text_composite_compare
from package_template_vxa import archive

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))

def validate(verification,reports,artifacts,text_report=None):
 if verification.get('passed') is not True:raise ValueError('Runtime verification has not passed')
 profiles=[('xp','xp-tile-submit'),('vxa','vxa-map-regression')] if text_report is not None else [('xp','xp-tile-cache'),('vxa','vxa-tile-parse')]
 for engine,profile in profiles:
  report=reports[engine]
  digest=artifacts[engine]['sha256']
  if verification['artifacts'][engine]['sha256']!=digest or report['hashes'][engine]['candidate']!=digest:raise ValueError('DLL differs from measured and verified artifact')
  if report.get('passed') is not True or report.get('profile')!=profile or len(report['results'])!=16:raise ValueError('Incomplete or failed tile performance report')
  if not all(row['passed'] for row in tile_compare(report['results'],profile)):raise ValueError('Tile performance thresholds failed')
  candidates=[r for r in report['results'] if r['build']=='candidate']
  if len(candidates)!=10 or not all(render_accepted(r) for r in candidates):raise ValueError('Output/logic acceptance failed')
  regressions=report.get('regressions',[])
  if len(regressions)!=2 or not all(r['passed'] and all(v<=1.1 for v in r['ratios'].values()) for r in regressions):raise ValueError('General/invalidated workload regression failed')
 if text_report is not None:
  if text_report.get('passed') is not True or text_report.get('profile')!='text-composite' or len(text_report.get('results',[]))!=48:raise ValueError('Incomplete or failed text performance report')
  for engine in ('xp','vxa'):
   if text_report['hashes'][engine]['candidate']!=artifacts[engine]['sha256']:raise ValueError('Text benchmark DLL differs')
  if not all(r['passed'] for r in text_composite_compare(text_report['results'])):raise ValueError('Text composition thresholds failed')


def package(output,verification_file,xp_report,vxa_report,text_report=None):
 output=Path(output).resolve()
 if output.exists():raise ValueError('Use a new output directory')
 native=ROOT/'build/runtime-native/bin/Release'
 artifacts={engine:inspect(native/name,engine=engine) for engine,name in [('xp','Lunetile.dll'),('vxa','LunetileVXA.dll')]}
 verification=read(verification_file);reports={'xp':read(xp_report),'vxa':read(vxa_report)}
 validate(verification,reports,artifacts,read(text_report) if text_report else None)
 output.mkdir(parents=True)
 diagnostics=output/'diagnostics';diagnostics.mkdir()
 for source,name in [(verification_file,'verification.json'),(xp_report,'xp-performance.json'),(vxa_report,'vxa-performance.json')]:shutil.copy2(source,diagnostics/name)
 if text_report:shutil.copy2(text_report,diagnostics/'text-performance.json')
 for source in (('docs/SUBMIT_TEXT_PERFORMANCE.md',) if text_report else ())+('docs/TILE_CLIENT_PERFORMANCE.md','docs/VALIDATION.md'):shutil.copy2(ROOT/source,diagnostics/Path(source).name)
 sources={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for directory in ('src/runtime','scripts','tests') for p in sorted((ROOT/directory).rglob('*')) if p.is_file() and p.suffix in ('.cpp','.h','.rb','.py','.json') and '__pycache__' not in p.parts}
 sources['CMakeLists.txt']=sha(ROOT/'CMakeLists.txt')
 (diagnostics/'source-sha256.json').write_text(json.dumps(sources,indent=2)+'\n',encoding='utf-8')
 for engine,name in [('xp','Lunetile.dll'),('vxa','LunetileVXA.dll')]:
  folder=output/engine;folder.mkdir();shutil.copy2(native/name,folder/name)
  shutil.copy2(ROOT/'LICENSE',folder/'LICENSE');shutil.copytree(ROOT/'licenses',folder/'licenses')
  (folder/'README.txt').write_text(f'Lunetile {engine.upper()} performance update\n\n게임을 종료한 뒤 기존 {name}을 보관하고 이 DLL로 교체하세요.\n다른 엔진의 DLL은 사용할 수 없습니다. Game.ini와 게임/저장 파일은 수정하지 않습니다.\n검증 범위와 수치는 동봉 진단 ZIP의 {'SUBMIT_TEXT_PERFORMANCE.md' if text_report else 'TILE_CLIENT_PERFORMANCE.md'}를 참고하세요.\nRTP는 포함하지 않습니다. 기존 템플릿의 설치 요구 사항을 유지합니다.\n',encoding='utf-8')
  (folder/'SHA256SUMS.json').write_text(json.dumps({name:sha(folder/name)},indent=2)+'\n',encoding='ascii')
  archive(folder,output/f'lunetile-{engine}-speed-fix.zip')
 archive(diagnostics,output/('lunetile-submit-text-diagnostics.zip' if text_report else 'lunetile-tile-performance-diagnostics.zip'))
 hashes={p.name:sha(p) for p in sorted(output.glob('*.zip'))}
 for path in output.glob('*.zip'):
  with zipfile.ZipFile(path) as z:
   if z.testzip() is not None:raise ValueError('ZIP CRC failure')
   if path.name.startswith('lunetile-xp-') or path.name.startswith('lunetile-vxa-'):
    name='Lunetile.dll' if '-xp-' in path.name else 'LunetileVXA.dll'
    if z.read(name)!=(native/name).read_bytes():raise ValueError('Packaged DLL mismatch')
 (output/'SHA256SUMS.txt').write_text(''.join(f'{v}  {k}\n' for k,v in hashes.items()),encoding='ascii')
 return hashes

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('output',type=Path);ap.add_argument('--verification',required=True,type=Path);ap.add_argument('--xp-performance',required=True,type=Path);ap.add_argument('--vxa-performance',required=True,type=Path)
 ap.add_argument('--text-performance',type=Path)
 args=ap.parse_args();print(json.dumps(package(args.output,args.verification,args.xp_performance,args.vxa_performance,args.text_performance),indent=2))
