"""Embed the pinned JSON Ruby files without MSVC string-literal size limits."""
import sys
from pathlib import Path

def embed(source, output):
 parts=['#pragma once\n']
 for name,path in [('version','json/version.rb'),('common','json/common.rb'),('state','json/ext/generator/state.rb'),('ext','json/ext.rb'),('root','json.rb')]:
  data=(source/'ext/json/lib'/path).read_bytes()+b'\0'
  parts.append('static void init_json_'+name+'() {\nstatic const unsigned char source[] = {\n')
  parts.extend(','.join(str(value) for value in data[i:i+32])+',\n' for i in range(0,len(data),32))
  parts.append('};\nrb_eval_string(reinterpret_cast<const char*>(source));\n}\n')
 output.write_text(''.join(parts),encoding='utf-8')

if __name__=='__main__':embed(Path(sys.argv[1]),Path(sys.argv[2]))
