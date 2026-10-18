"""Separate diagnostic pass; never mix this instrumented run into the paired frame comparison."""
import argparse,json
from pathlib import Path
from benchmark_runtime import run_case
from test_runtime import ROOT
from rxdata import read
from migrate_project import transform

def main():
 ap=argparse.ArgumentParser();ap.add_argument('project',type=Path);ap.add_argument('fixture',type=Path);ap.add_argument('dll',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--frames',type=int,default=240)
 a=ap.parse_args();out=a.output.resolve();out.parent.mkdir(parents=True,exist_ok=True)
 entries=read((a.project/'Data/Scripts.rxdata').read_bytes());patches,_=transform(entries)
 code=b'\n'.join(patches.get(i,e.source()) for i,e in enumerate(entries[:-1]))+b'\n'+(ROOT/'tests/runtime_render_profile.rb').read_bytes()+b'\n'+(ROOT/'tests/runtime_bench.rb').read_bytes()
 report=run_case(a.fixture.resolve(),(a.project/'Game.exe').resolve(),a.dll.resolve(),ROOT/'build/runtime-native/bin/Release/RGSSBenchMetrics.dll',code,out,a.frames,True)
 print('Rendering wall-time partition + GPU query diagnostic PASS')

if __name__=='__main__':main()
