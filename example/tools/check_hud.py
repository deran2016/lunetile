"""Check HUD and minimap pixels in the actual Windows launcher using generated atlases."""
import argparse,json
from pathlib import Path
from prepare_example import ROOT
from test_runtime import run

def verify(output):
 output=output.resolve()
 source=b'# encoding: UTF-8\n'+b'\n'.join((ROOT/'example/client'/name).read_bytes() for name in ['mmo_hud.rb','mmo_ui.rb'])
 source+=b'\n'+(ROOT/'tests/runtime_mmo_hud.rb').read_bytes()
 try:
  result=run(ROOT/'template-xp/Game.exe',ROOT/'build/runtime-native/bin/Release/Lunetile.dll',output,'',source,
   screen_size=(1280,720),timing_profile='stock120',data_encoding='UTF-8',timeout=40)
 except AssertionError as error:
  if error.args and isinstance(error.args[0],dict):raise RuntimeError(error.args[0].get('log','HUD launcher failed')) from None
  raise
 report=json.loads((output/'hud-pixels.json').read_text())
 report['dll_sha256']=result['runtime_sha256']
 (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
 args=parser.parse_args();verify(args.output);print('HUD opacity, 48px layout, 192 autotile quarters, layer priority, alpha and minimap lifetime PASS')
