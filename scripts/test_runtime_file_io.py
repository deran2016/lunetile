"""Verify native-only disk reads, bounded archive indexing and failure boundaries."""
import argparse,json,sys,struct
from pathlib import Path
from test_runtime import ROOT,run,sha,ORIGINAL_EXE
sys.path.insert(0,str(ROOT/'tests'))
from rgssad_fixture import pack

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 for name in ('exe','dll','output'):ap.add_argument(name,type=Path)
 a=ap.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 exe=a.exe.resolve();dll=a.dll.resolve();assert sha(exe)==ORIGINAL_EXE
 before={str(p):sha(p) for p in (exe,dll)}
 fixtures=out/'fixtures';fixtures.mkdir()
 long_file=fixtures.joinpath(*['p'*60+str(i) for i in range(5)],'한글.bin')
 long_file.parent.mkdir(parents=True);long_file.write_bytes(bytes(range(256))*9)
 entries=[(b'Padding.bin',b'p'*70000)]
 entries += [(('Data/entry'+str(i)+'.bin').encode(),('entry:'+str(i)+':').encode()*(1+i%9)) for i in range(2000)]
 blobs={'fixture':pack(entries),'bad-version':b'RGSSAD\0\x03','truncated':b'RGSSAD\0\x01xx','bad-length':b'RGSSAD\0\x01'+struct.pack('<I',4097^0xdeadcafe),'bad-name':pack([(b'../bad',b'x')]),'duplicate':pack([(b'same',b'x'),(b'same',b'y')])}
 for name,data in blobs.items():(fixtures/(name+'.rgssad')).write_bytes(data)
 result=run(exe,dll,out/'runtime','',(ROOT/'tests/runtime_file_io.rb').read_bytes(),data=fixtures,timeout=60)
 owner,worker,jobs,index_jobs,path_length=map(int,(out/'runtime/file-io-result.txt').read_text().split(','))
 assert owner!=worker and owner>0 and worker>0 and jobs>10 and 0<index_jobs<100 and path_length>260
 assert before=={str(p):sha(p) for p in (exe,dll)}
 report={'passed':True,'dll_sha256':result['runtime_sha256'],'caller_thread_id':owner,'last_worker_thread_id':worker,'native_read_jobs':jobs,'archive_index_jobs':index_jobs,'archive_entries':2001,'long_relative_path_characters':path_length,'inputs_preserved':True,'probe_sha256':sha(ROOT/'tests/runtime_file_io.rb'),'scope':'Actual native worker reads; binary/empty/ranged/Korean paths and direct native long-path read, large-file limit, bounded 64KiB metadata-cache fills across 2001 archive entries, missing/invalid paths and malformed/changed archives. General Ruby File/Dir and resolved asset paths over 260 characters are not certified. Ruby object construction stays on caller; synchronous API, not nonblocking loading or proof against same-size concurrent file mutation.'}
 (out/'summary.json').write_text(json.dumps(report,indent=2));print('Native file I/O and archive boundaries: PASS')

if __name__=='__main__':main()
