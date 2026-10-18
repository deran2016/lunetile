"""Verify the x86 PE launcher contract without loading the DLL."""
import argparse,hashlib,json,struct
from pathlib import Path

class PE:
 def __init__(self,path):
  self.data=path.read_bytes()
  if self.data[:2]!=b'MZ':raise ValueError('Not a PE image')
  pe=self.u32(0x3c)
  if self.data[pe:pe+4]!=b'PE\0\0':raise ValueError('Invalid PE signature')
  self.machine=self.u16(pe+4);count=self.u16(pe+6);size=self.u16(pe+20)
  optional=pe+24
  if self.u16(optional)!=0x10b:raise ValueError('Expected PE32 optional header')
  self.directories=optional+96
  self.sections=[]
  for index in range(count):
   offset=optional+size+40*index
   virtual_size,rva,raw_size,raw=struct.unpack_from('<4I',self.data,offset+8)
   self.sections.append((rva,max(virtual_size,raw_size),raw,raw_size))
 def u16(self,offset):return struct.unpack_from('<H',self.data,offset)[0]
 def u32(self,offset):return struct.unpack_from('<I',self.data,offset)[0]
 def offset(self,rva):
  for base,size,raw,raw_size in self.sections:
   if base<=rva<base+size:
    if rva-base>=raw_size:raise ValueError('RVA has no file bytes')
    return raw+rva-base
  raise ValueError(f'Unmapped RVA {rva:x}')
 def text(self,rva):
  start=self.offset(rva);end=self.data.index(0,start)
  return self.data[start:end].decode('ascii')
 def directory(self,index):return struct.unpack_from('<II',self.data,self.directories+8*index)
 def exports(self):
  base,size=self.directory(0)
  if not base:return []
  offset=self.offset(base)
  ordinal,functions,names,functions_rva,names_rva,ordinals_rva=struct.unpack_from('<6I',self.data,offset+16)
  result=[]
  for index in range(names):
   name=self.text(self.u32(self.offset(names_rva)+4*index))
   slot=self.u16(self.offset(ordinals_rva)+2*index)
   if slot>=functions:raise ValueError('Invalid export ordinal')
   address=self.u32(self.offset(functions_rva)+4*slot)
   result.append({'name':name,'ordinal':ordinal+slot,'forwarded':base<=address<base+size})
  return sorted(result,key=lambda item:item['ordinal'])
 def imports(self):
  rva,size=self.directory(1)
  if not rva:return []
  offset=self.offset(rva);result=[]
  for index in range(size//20):
   descriptor=struct.unpack_from('<5I',self.data,offset+20*index)
   if not any(descriptor):return result
   result.append(self.text(descriptor[3]))
  raise ValueError('Unterminated import table')

def inspect(path):
 root=Path(__file__).resolve().parents[1]
 abi=json.loads((root/'src/runtime/abi.json').read_text())
 pe=PE(path)
 if pe.machine!=0x14c:raise ValueError('DLL must be x86')
 exports=pe.exports();imports=pe.imports()
 expected={(item['name'],item['ordinal']) for item in abi['exports']}
 if not expected.issubset({(item['name'],item['ordinal']) for item in exports}):raise ValueError('Missing launcher export or incorrect ordinal')
 if any(item['forwarded'] for item in exports):raise ValueError('Runtime cannot forward exports')
 if any('rgss' in item.lower() or 'ruby' in item.lower() or 'mkxp' in item.lower() for item in imports):raise ValueError('Unexpected engine/Ruby DLL dependency')
 return {'format':'PE32','machine':'x86','sha256':hashlib.sha256(pe.data).hexdigest(),'exports':exports,'upstream_private_exports':[item['name'] for item in exports if item['name'] not in {name for name,ordinal in expected}],'imports':imports}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('dll',type=Path);ap.add_argument('--output',type=Path)
 a=ap.parse_args();text=json.dumps(inspect(a.dll),indent=2)+'\n'
 if a.output:a.output.write_text(text)
 print(text)

if __name__=='__main__':main()
