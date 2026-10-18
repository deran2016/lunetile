"""Compare finite cache, hue and animation observations with the original DLL."""
import argparse,json,subprocess,sys
from pathlib import Path
from test_runtime import ROOT,run,sha,ORIGINAL_EXE,ORIGINAL_DLL
from test_runtime_graphics import records

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ('exe','original','replacement','output'):ap.add_argument(name,type=Path)
 a=ap.parse_args();exe,old,new=[p.resolve() for p in (a.exe,a.original,a.replacement)]
 assert sha(exe)==ORIGINAL_EXE and sha(old)==ORIGINAL_DLL and sha(new)!=ORIGINAL_DLL
 before={str(p):sha(p) for p in (exe,old,new)}
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 probe=ROOT/'tests/rgss_graphics_helpers_reference.rb'
 with (out/'original.log').open('w') as log:
  subprocess.run([sys.executable,str(ROOT/'scripts/probe_original_types.py'),str(exe),str(old),str(out/'original'),'--probe',str(probe)],check=True,stdout=log,stderr=subprocess.STDOUT)
 result=run(exe,new,out/'replacement','',probe.read_bytes()+b"\nFile.write('runtime-complete.txt','helpers,false,false');sleep 0.5\n")
 for folder in ('original','replacement'):assert not (out/folder/'helper-error.txt').exists(),(out/folder/'helper-error.txt').read_text()
 original=records(out/'original/types-reference.txt');replacement=records(out/'replacement/types-reference.txt')
 expected={'cache_shared_lifetime','cache_recreated'}|{'hue_'+str(h) for h in (-120,0,60,180,360,720)}|{prefix+kind+str(p) for prefix in ('','odd_') for p in range(4) for kind in ('animation_','animation_stopped_','loop_','loop_stopped_')}
 differences=sorted(k for k in original.keys()|replacement.keys() if original.get(k)!=replacement.get(k))
 coverage=set(original)==set(replacement)==expected
 assert before=={str(p):sha(p) for p in (exe,old,new)}
 geometry=[k for k in differences if not k.startswith('hue_')]
 hue_checks=[]
 for hue in (-120,0,60,180,360):
  left,right=original['hue_'+str(hue)],replacement['hue_'+str(hue)]
  error=max(abs(x-y) for a,b in zip(left,right) for x,y in zip(a[:3],b[:3]))
  alpha=all(a[3]==b[3] for a,b in zip(left,right))
  hue_checks.append({'hue':hue,'max_rgb_channel_error':error,'alpha_exact':alpha,'passed':error<=3 and alpha})
 report={'passed':coverage and not geometry and all(row['passed'] for row in hue_checks),'coverage_complete':coverage,'dll_sha256':result['runtime_sha256'],'original_sha256':ORIGINAL_DLL,'exact_matching_records':len(expected)-len(differences),'different_records':differences,'geometry_differences':geometry,'hue_checks':hue_checks,'hue_channel_tolerance':3,'out_of_range_hue_720_exact':original['hue_720']==replacement['hue_720'],'probe_sha256':sha(probe),'inputs_preserved':True,'scope':'Cache lifetime and four-position three-frame animation/loop public states exact. Hue RGB uses a three-level quality bound, alpha exact, not byte-identical legacy hue quantization. 720-degree behavior recorded but outside supported 0..360 data range. No timing sounds, screen-flash pixels or arbitrary animations.'}
 (out/'summary.json').write_text(json.dumps(report,indent=2));assert report['passed'],report
 print('Original/replacement finite graphics helper observations: PASS ('+str(len(expected))+' records)')

if __name__=='__main__':main()
