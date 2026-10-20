"""Compare stock VX Ace FPS in sequential visible launcher runs on one PC."""
import argparse,ctypes,json,shutil,statistics
from pathlib import Path
from test_runtime_vxa import ROOT,run
from rxdata import read
from package_template_vxa import expand_map
from inspect_runtime import inspect

def accepted(result):
 rate=result['render_rate']
 minimum=118 if rate==120 else rate*.98
 return (119 <= result['logic_fps'] <= 121 and result['present_fps'] >= minimum
         and result['missing_fraction'] <= .02 and result['command_ms']['p95'] <= 4)

def reductions(results,profile='tile-cache'):
 comparisons=[]
 for moving in (False,True):
  groups=[[r for r in results if r['build']==label and r['moving']==moving and r['render_rate']==120 and r.get('scenario','stock')=='stock'] for label in ('baseline','optimized')]
  old,new=groups
  cpu=statistics.mean(r['combined_ms']['mean'] for r in new)/statistics.mean(r['combined_ms']['mean'] for r in old)
  allocation=statistics.mean(r['allocated_per_present'] for r in new)/statistics.mean(r['allocated_per_present'] for r in old)
  comparison={'moving':moving,'cpu_ratio':cpu,'allocation_ratio':allocation,'passed':cpu<=.7 and allocation<=.5}
  if profile=='tile-d3d':
   submit=statistics.mean(r['submit_ms']['mean'] for r in new)/statistics.mean(r['submit_ms']['mean'] for r in old)
   total=statistics.mean(r['total_ms']['mean'] for r in new)/statistics.mean(r['total_ms']['mean'] for r in old)
   p95=max(r['total_ms']['p95']/next(b['total_ms']['p95'] for b in old if b.get('repeat',0)==r.get('repeat',0)) for r in new)
   draws=statistics.mean(r['batches']['tile_draws'] for r in new)/statistics.mean(r['batches']['tile_quads'] for r in new)
   comparison.update(submit_ratio=submit,total_ratio=total,total_p95_ratio_max=p95,tile_draw_ratio=draws,
    passed=submit<=.7 and total<=.9 and p95<=1.05 and allocation<=1.05 and draws<=.1 and all(r['batches']['instance_maps']<=1 for r in new))
  comparisons.append(comparison)
 return comparisons

def unbatchable_comparison(results):
 old,new=[[r for r in results if r['build']==label and r.get('scenario')=='alternating'] for label in ('baseline','optimized')]
 total=statistics.mean(r['total_ms']['mean'] for r in new)/statistics.mean(r['total_ms']['mean'] for r in old)
 submit=statistics.mean(r['submit_ms']['mean'] for r in new)/statistics.mean(r['submit_ms']['mean'] for r in old)
 p95=max(r['total_ms']['p95']/next(b['total_ms']['p95'] for b in old if b['repeat']==r['repeat']) for r in new)
 return {'total_ratio':total,'submit_ratio':submit,'total_p95_ratio_max':p95,'passed':total<=1.05 and p95<=1.05}

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('output',type=Path);ap.add_argument('--baseline',type=Path,required=True)
 ap.add_argument('--profile',choices=('tile-cache','tile-d3d'),default='tile-cache')
 args=ap.parse_args();out=args.output.resolve();out.mkdir(exist_ok=False)
 fixture=out/'fixture';shutil.copytree(ROOT/'template-vxa/Data',fixture/'Data')
 expand_map(fixture,ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe',out)
 entries=read((ROOT/'template-vxa/Data/Scripts.rvdata2').read_bytes())
 definitions=b'\n'.join(e.source().replace(b'\r\r\n',b'\n') for e in entries if e.name!=b'Main')
 code=definitions+b'\n'+(ROOT/'src/runtime/vxa_stock.rb').read_bytes()+b'\n'
 probe=(ROOT/'tests/runtime_vxa_fps.rb').read_bytes()
 candidate=ROOT/'build/runtime-native/bin/Release/LunetileVXA.dll'
 user=ctypes.windll.user32;gdi=ctypes.windll.gdi32
 user.GetDC.restype=ctypes.c_void_p;user.GetDC.argtypes=[ctypes.c_void_p]
 gdi.GetDeviceCaps.argtypes=[ctypes.c_void_p,ctypes.c_int]
 user.ReleaseDC.argtypes=[ctypes.c_void_p,ctypes.c_void_p]
 dc=user.GetDC(None)
 try:refresh=gdi.GetDeviceCaps(dc,116)
 finally:user.ReleaseDC(None,dc)
 results=[]
 for moving in (False,True):
  for repeat in range(3):
   for label,dll in [('baseline',args.baseline.resolve()),('optimized',candidate)]:
    folder=out/f'{label}-{int(moving)}-{repeat}'
    source=code+f'FPS_MOVING={str(moving).lower()}; FPS_SECONDS=30\n'.encode()+probe
    run(folder,source,dll=dll,high=True,wide=True,rate=120,rtp=True,data=fixture/'Data',timeout=90)
    result=json.loads((folder/'fps.json').read_text());result.update(build=label,repeat=repeat)
    results.append(result);print(json.dumps(result),flush=True)
 for rate in (40,60):
  for moving in (False,True):
   folder=out/f'optimized-{rate}-{int(moving)}'
   source=code+f'FPS_MOVING={str(moving).lower()}; FPS_SECONDS=10\n'.encode()+probe
   run(folder,source,dll=candidate,high=True,wide=True,rate=rate,rtp=True,data=fixture/'Data',timeout=45)
   result=json.loads((folder/'fps.json').read_text());result.update(build='optimized',repeat=0)
   results.append(result);print(json.dumps(result),flush=True)
 if args.profile=='tile-d3d':
  for repeat in range(3):
   for label,dll in [('baseline',args.baseline.resolve()),('optimized',candidate)]:
    folder=out/f'{label}-alternating-{repeat}'
    source=code+b'FPS_ALTERNATING=true; FPS_MOVING=false; FPS_SECONDS=10\n'+probe
    run(folder,source,dll=dll,high=True,wide=True,rate=120,rtp=True,data=fixture/'Data',timeout=45)
    result=json.loads((folder/'fps.json').read_text());result.update(build=label,repeat=repeat,scenario='alternating')
    results.append(result);print(json.dumps(result),flush=True)
 comparisons=reductions(results,args.profile)
 report={'passed':all(accepted(r) for r in results if r['build']=='optimized') and all(r['passed'] for r in comparisons),
         'reductions':comparisons,
         'profile':args.profile,
         'candidate_sha256':inspect(candidate,engine='vxa')['sha256'],
         'baseline_sha256':inspect(args.baseline,engine='vxa')['sha256'],
         'primary_display_nominal_hz':refresh,
         'measurement':'Successful DXGI Present submissions, not physical scan-out; visible window, focus pause disabled',
         'results':results}
 if args.profile=='tile-d3d':
  report['unbatchable']=unbatchable_comparison(results)
  report['passed']=report['passed'] and report['unbatchable']['passed']
 (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 assert report['passed'],'VXA FPS acceptance failed; inspect summary.json'
 print('VXA FPS acceptance PASS',flush=True)

if __name__=='__main__':main()
