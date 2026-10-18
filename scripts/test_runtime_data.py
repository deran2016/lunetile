"""Compare every supplied project data graph with the original engine reference."""
import argparse,ast,json
from pathlib import Path
from test_runtime import ROOT,run

def read_graphs(path):
 graphs={}
 for line in path.read_text().splitlines():
  name,value=line.split('\t',1)
  graphs[name]=ast.literal_eval(value.replace('nil','None').replace('false','False').replace('true','True'))
 return graphs

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('exe',type=Path);ap.add_argument('dll',type=Path)
 ap.add_argument('data',type=Path);ap.add_argument('reference',type=Path);ap.add_argument('output',type=Path)
 a=ap.parse_args()
 result=run(a.exe.resolve(),a.dll.resolve(),a.output.resolve(),'',(ROOT/'tests/runtime_data.rb').read_bytes(),data=a.data)
 expected=read_graphs(a.reference/'types-reference.txt')
 actual=read_graphs(a.output/'types-reference.txt')
 assert expected and actual==expected,{'matching':[name for name in expected if actual.get(name)==expected[name]],'mismatching':[name for name in expected if actual.get(name)!=expected[name]]}
 report={'passed':True,'data_files':len(actual),'nodes':sum(len(v) for v in actual.values()),'runtime':result}
 (a.output/'comparison.json').write_text(json.dumps(report,indent=2))
 print(f'Original/new engine project data graphs and Marshal roundtrips: {len(actual)} files PASS')

if __name__=='__main__':main()
