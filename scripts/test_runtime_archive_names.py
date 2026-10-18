"""Explicit UTF-8/CP949/CP932 archive filename decoding, including a Shift-JIS 0x5c trail byte."""
import argparse,json,subprocess,sys
from pathlib import Path
from test_runtime import ROOT,run,sha,ORIGINAL_EXE
from test_runtime_rtp import png
from rxdata import string
sys.path.insert(0,str(ROOT/'tests'))
from rgssad_fixture import pack

CASES=[('UTF-8','utf-8','한글ソフィア'),('CP949','cp949','한글'),('CP932','cp932','ソフィア')]

def normalize_probe(ruby,out):
 script=out/'normalize.rb'
 script.write_text("module RGSSXP; DATA_ENCODING=ARGV.shift; end\nload 'src/runtime/text.rb'\nload 'src/runtime/data.rb'\nload 'src/runtime/archive.rb'\nlabel=ARGV.shift\nraw=label.encode(RGSSXP::SOURCE_ENCODING).b\nleft=RGSSXP::Archive.normalize(raw);right=RGSSXP::Archive.normalize(label)\nputs [left.unpack1('H*'),right.unpack1('H*')].join('|')\nexit(left==right ? 0 : 1)\n",encoding='utf-8')
 results=[]
 for encoding,codec,label in CASES:
  process=subprocess.run([str(ruby),'--disable-gems',str(script),encoding,label],cwd=ROOT,capture_output=True,text=True)
  results.append({'encoding':encoding,'label':label,'passed':process.returncode==0,'stdout':process.stdout.strip(),'stderr':process.stderr})
 report={'passed':all(row['passed'] for row in results),'source_sha256':sha(ROOT/'src/runtime/archive.rb'),'cases':results,'scope':'Ruby CLI loads the actual archive normalizer source; no native DLL, file-reader or image/audio execution proof.'}
 (out/'normalize-summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 return report

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ('exe','dll','output'):ap.add_argument(name,type=Path)
 ap.add_argument('--normalize-only',type=Path,metavar='RUBY',help='No game window: check only the current normalizer source with this Ruby CLI')
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 if a.normalize_only:
  report=normalize_probe(a.normalize_only.resolve(),out);print(json.dumps(report,ensure_ascii=False,indent=2));assert report['passed'],report;return
 exe=a.exe.resolve();dll=a.dll.resolve();assert sha(exe)==ORIGINAL_EXE
 before={str(p):sha(p) for p in (exe,dll)};results=[]
 for encoding,codec,label in CASES:
  case=out/encoding;case.mkdir();data=case/'fixtures';data.mkdir()
  (data/'label.txt').write_text(label,encoding='utf-8')
  entries=[(('Data/'+label+'.rxdata').encode(codec),b'\x04\x08'+string((label+' payload').encode(codec))), (('Graphics/Pictures/'+label+'.png').encode(codec),png()), (('Audio/BGM/'+label+'.wav').encode(codec),b'own audio fixture')]
  blob=pack(entries);(data/'names.rgssad').write_bytes(blob)
  invalid=b'\xff' if encoding=='UTF-8' else b'\x80' if encoding=='CP949' else b'\x81'
  (data/'invalid-name.rgssad').write_bytes(pack([(b'Data/'+invalid+b'.bin',b'x')]))
  result=run(exe,dll,case/'runtime','',(ROOT/'tests/runtime_archive_names.rb').read_bytes(),data=data,data_encoding=encoding)
  assert (case/'runtime/archive-names-result.txt').read_text(encoding='utf-8')==label
  assert (case/'runtime/Data/names.rgssad').read_bytes()==blob
  results.append({'encoding':encoding,'label':label,'archive_sha256':sha(data/'names.rgssad'),'passed':True,'dll_sha256':result['runtime_sha256']})
 assert before=={str(p):sha(p) for p in (exe,dll)}
 report={'passed':True,'dll_sha256':sha(dll),'cases':results,'inputs_preserved':True,'probe_sha256':sha(ROOT/'tests/runtime_archive_names.rb'),'scope':'Own RGSSAD filenames in explicit UTF-8/CP949/CP932, Shift-JIS 0x5c trail byte, normalized data, extensionless PNG and opaque audio bytes. No original-system-locale or acoustic comparison; archive bytes preserved.'}
 (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print('Explicit encoded archive filenames: PASS')

if __name__=='__main__':main()
