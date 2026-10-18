"""Recheck completed endurance samples without rerunning or changing the game."""
import argparse,json
from test_runtime import sha,ORIGINAL_DLL
from test_runtime_stock_boot import ROOT,endurance_result
from pathlib import Path

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('project',type=Path);a=ap.parse_args();out=a.project.resolve()
 source=out/'boot-result.json';report=json.loads(source.read_text())
 target=out/'endurance-review.json'
 if target.exists():raise FileExistsError(target)
 assert report['passed'] and report['dll_sha256']==sha(out/'RGSS104E.dll')!=ORIGINAL_DLL
 old=report['endurance'];assert old['meets_duration_and_roundtrip_gate']
 samples=json.loads((out/'memory-samples.json').read_text());images=json.loads((out/'modules.json').read_text())
 assert report['dll_sha256'] in images.values()
 report['endurance']=endurance_result(out,samples,images,old['requested_seconds'],old['requested_roundtrips'])
 report['review_inputs']={name:sha(out/name) for name in ('boot-result.json','memory-samples.json','modules.json','endurance-result.txt')}
 report['review_source_sha256']=sha(Path(__file__))
 report['analysis_source_sha256']=sha(ROOT/'scripts/test_runtime_stock_boot.py')
 report['scope']+='; separate early-map-load and post-warmup memory windows'
 target.write_text(json.dumps(report,indent=2))
 print('Endurance duration, roundtrips, module identity and both memory windows: PASS')

if __name__=='__main__':main()
