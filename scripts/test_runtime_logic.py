"""Compare bounded stock logic with fixed test RNG; no rendering/audio fidelity claim."""
import argparse,hashlib,json,math,subprocess,sys
from pathlib import Path
from test_runtime import ROOT,run,sha,ORIGINAL_DLL,ORIGINAL_EXE
from test_runtime_graphics import records
from migrate_project import transform
from rxdata import read

REQUIRED={'contact_started','contact_result','decision_result','autorun_result','blocked_tile','through_tile','timer_state','map_setup','tied_battle_order','skill_result','item_result','state_result'}
REQUIRED.update('forced_route_'+str(i) for i in range(0,120,10))
REQUIRED.update('screen_'+str(i) for i in range(6))
REQUIRED.update(name+'_'+str(i) for name in ('enemy_action','actor_attack','enemy_attack','battle_order') for i in range(6))

def equivalent(left,right):
 if type(left) is not type(right):return False
 if isinstance(left,float):return math.isclose(left,right,rel_tol=0,abs_tol=1e-12)
 if isinstance(left,list):return len(left)==len(right) and all(equivalent(a,b) for a,b in zip(left,right))
 return left==right

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('project',type=Path);ap.add_argument('original',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('output',type=Path)
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 exe=(a.project/'Game.exe').resolve();original=a.original.resolve();dll=a.dll.resolve()
 assert sha(exe)==ORIGINAL_EXE and sha(original)==ORIGINAL_DLL and sha(dll)!=ORIGINAL_DLL
 inputs=[exe,original,dll,a.project/'Data/Scripts.rxdata'];before={str(p):sha(p) for p in inputs}
 entries=read((a.project/'Data/Scripts.rxdata').read_bytes());replacements,_=transform(entries)
 probe=(ROOT/'tests/rgss_logic_reference.rb').read_bytes();selected=list(enumerate(entries[:-1]))
 probe=b"begin\n"+probe+b"\nrescue Exception => error\nFile.open('logic-error.txt','w'){|file|file.puts(error.class.name+': '+error.message);file.puts(error.backtrace)}\nexit 1\nend\n"
 old=b'\n'.join(entry.source() for _,entry in selected)+b'\n'+probe
 reference=out/'logic-probe.rb';reference.write_bytes(old)
 command=[sys.executable,str(ROOT/'scripts/probe_original_types.py'),str(exe),str(original),str(out/'original'),'--probe',str(reference),'--data',str((a.project/'Data').resolve())]
 with (out/'original.log').open('w') as log:subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT)
 new=b'\n'.join(replacements.get(i,entry.source()) for i,entry in selected)+b'\n'+probe+b"\nFile.write('runtime-complete.txt','logic,false,false');sleep 0.3\n"
 result=run(exe,dll,out/'replacement','',new,data=out/'original/Data')
 expected=records(out/'original/types-reference.txt');actual=records(out/'replacement/types-reference.txt')
 differences=sorted(key for key in expected.keys()|actual.keys() if key not in expected or key not in actual or not equivalent(actual[key],expected[key]))
 coverage=set(expected)==set(actual)==REQUIRED
 report={'passed':not differences and coverage,'coverage_complete':coverage,'dll_sha256':result['runtime_sha256'],'original_sha256':ORIGINAL_DLL,'matching_records':sum(k in actual and equivalent(actual[k],v) for k,v in expected.items()),'different_records':differences,'missing_original_records':sorted(REQUIRED-set(expected)),'missing_replacement_records':sorted(REQUIRED-set(actual)),'probe_sha256':hashlib.sha256(probe).hexdigest(),'float_absolute_tolerance':1e-12,'scope':'Fixed 37-percent test RNG; stock contact/decision/parallel/autorun, passability/through, forced route/jump, timer, screen state, map setup, six battle orders/enemy choices/basic attacks, twelve tied action speeds, one skill/item/slip-state case. Types and non-floats match exactly; float text differences bounded by 1e-12. Direct logic calls only; not full scenes, arbitrary RNG or rendering/audio certification.'}
 assert before=={str(p):sha(p) for p in inputs},'An input changed'
 report['originals_preserved']=True
 (out/'summary.json').write_text(json.dumps(report,indent=2))
 assert report['passed'],report
 print('Original/replacement deterministic stock logic: PASS ('+str(len(expected))+' records)')

if __name__=='__main__':main()
