"""Compare owned damage text and viewport animation observations, retaining pixel diagnostics."""
import argparse,json,subprocess,sys
from pathlib import Path
from test_runtime import ROOT,run,sha,ORIGINAL_EXE,ORIGINAL_DLL
from test_runtime_graphics import records

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ('exe','original','dll','output'):ap.add_argument(name,type=Path)
 a=ap.parse_args();exe,old,new=[p.resolve() for p in (a.exe,a.original,a.dll)]
 assert sha(exe)==ORIGINAL_EXE and sha(old)==ORIGINAL_DLL
 before={str(p):sha(p) for p in (exe,old,new)}
 out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);probe=ROOT/'tests/rgss_graphics_extended_reference.rb'
 with (out/'original.log').open('w') as log:subprocess.run([sys.executable,str(ROOT/'scripts/probe_original_types.py'),str(exe),str(old),str(out/'original'),'--probe',str(probe)],check=True,stdout=log,stderr=subprocess.STDOUT)
 result=run(exe,new,out/'replacement','',probe.read_bytes()+b"\nFile.write('runtime-complete.txt','extended,false,false');sleep 0.3\n")
 for folder in ('original','replacement'):assert not (out/folder/'extended-error.txt').exists(),(out/folder/'extended-error.txt').read_text()
 left=records(out/'original/types-reference.txt');right=records(out/'replacement/types-reference.txt')
 expected={kind+str(i) for i in range(3) for kind in ('damage_font_','damage_bounds_','damage_pixels_','screen_animation_','screen_loop_')}
 assert set(left)==set(right)==expected
 different=sorted(key for key in expected if left[key]!=right[key]);public=[key for key in different if not key.startswith('damage_pixels_')]
 assert before=={str(p):sha(p) for p in (exe,old,new)}
 report={'passed':not public,'dll_sha256':result['runtime_sha256'],'original_sha256':ORIGINAL_DLL,'original_records':left,'replacement_records':right,'different_records':different,'public_differences':public,'probe_sha256':sha(probe),'inputs_preserved':True,'scope':'Three default damage text font/color/bounds cases and screen-position animations/loops in three viewport sizes exact. Pixel hashes retained separately, not a font rasterization identity certificate.'}
 (out/'summary.json').write_text(json.dumps(report,indent=2));assert report['passed'],report
 print('Original/replacement extended graphics public observations: PASS')

if __name__=='__main__':main()
