"""Read-only RGSSAD v1 index for explicit project migration, not an engine dependency."""
import struct

class Archive:
 def __init__(self,path):
  self.path=path;self.entries={}
  with path.open('rb') as stream:
   if stream.read(8)!=b'RGSSAD\0\1':raise ValueError('Only RGSSAD v1 is supported')
   self.size=path.stat().st_size;key=0xdeadcafe
   while stream.tell()<self.size:
    length=self.word(stream)^key;key=self.step(key)
    if not 1<=length<=4096:raise ValueError('Invalid archive filename length')
    encrypted=stream.read(length)
    if len(encrypted)!=length:raise ValueError('Truncated archive filename')
    name=bytearray()
    for byte in encrypted:name.append(byte^(key&255));key=self.step(key)
    name=self.normalize(bytes(name))
    if b'\0' in name or b':' in name or any(part in (b'',b'.',b'..') for part in name.split(b'/')):raise ValueError('Invalid archive path')
    length=self.word(stream)^key;key=self.step(key)
    if length>self.size-stream.tell():raise ValueError('Archive entry exceeds file bounds')
    if name in self.entries:raise ValueError('Duplicate archive path')
    if len(self.entries)>=100000:raise ValueError('Too many archive entries')
    self.entries[name]=(stream.tell(),length,key)
    stream.seek(length,1)
 @staticmethod
 def step(key):return (key*7+3)&0xffffffff
 @staticmethod
 def normalize(name):
  if isinstance(name,str):name=name.encode('utf-8')
  return name.replace(b'\\',b'/').lower()
 @staticmethod
 def word(stream):
  raw=stream.read(4)
  if len(raw)!=4:raise ValueError('Truncated archive word')
  return struct.unpack('<I',raw)[0]
 def read(self,name):
  try:offset,length,key=self.entries[self.normalize(name)]
  except KeyError as error:raise ValueError(f'Archive entry not found: {name}') from error
  if length>128*1024*1024:raise ValueError('Archive entry exceeds 128 MiB')
  with self.path.open('rb') as stream:
   if self.path.stat().st_size!=self.size:raise ValueError('Archive changed after indexing')
   stream.seek(offset);encrypted=stream.read(length)
  if len(encrypted)!=length:raise ValueError('Truncated archive data')
  result=bytearray(length)
  for index,byte in enumerate(encrypted):
   result[index]=byte^((key>>((index%4)*8))&255)
   if index%4==3:key=self.step(key)
  return bytes(result)
