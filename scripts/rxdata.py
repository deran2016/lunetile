"""Bounded reader/writer for XP script arrays; retains every untouched entry's bytes."""
import zlib
from dataclasses import dataclass

def integer(value):
 if value==0:return b'\0'
 if 0<value<123:return bytes([value+5])
 if -124<value<0:return bytes([(value-5)&255])
 if not -0x80000000<=value<=0x7fffffff:raise ValueError('Marshal integer exceeds int32')
 if value>0:
  raw=value.to_bytes((value.bit_length()+7)//8,'little');return bytes([len(raw)])+raw
 for size in range(1,5):
  if -(1<<(8*size))<=value:
   return bytes([256-size])+(value&((1<<(8*size))-1)).to_bytes(size,'little')
 raise ValueError('Cannot encode integer')

def string(value):return b'"'+integer(len(value))+value

@dataclass
class Entry:
 id:int
 name:bytes
 compressed:bytes
 raw:bytes
 payload_span:tuple|None=None

 def source(self):
  decoder=zlib.decompressobj()
  try:source=decoder.decompress(self.compressed,16*1024*1024+1)
  except zlib.error as error:raise ValueError(f'Invalid zlib script: {error}') from error
  if len(source)>16*1024*1024 or not decoder.eof or decoder.unused_data:
   raise ValueError('Invalid or oversized zlib script')
  return source

class Reader:
 def __init__(self,data):self.data=data;self.pos=0;self.objects=[];self.symbols=[];self.string_spans={}
 def take(self,size):
  if size<0 or size>len(self.data)-self.pos:raise ValueError(f'Truncated Marshal at {self.pos}')
  value=self.data[self.pos:self.pos+size];self.pos+=size;return value
 def number(self):
  prefix=int.from_bytes(self.take(1),'little',signed=True)
  if prefix==0:return 0
  if prefix>4:return prefix-5
  if prefix<-4:return prefix+5
  raw=self.take(abs(prefix))
  return int.from_bytes(raw,'little')-((1<<(8*len(raw))) if prefix<0 else 0)
 def object(self,depth=0):
  if depth>8:raise ValueError('Script nesting exceeds schema')
  start=self.pos
  kind=self.take(1)
  if kind==b'i':return self.number()
  if kind==b'T':return True
  if kind==b'F':return False
  if kind==b'"':
   value=self.take(self.number());self.objects.append(value);self.string_spans[id(value)]=(start,self.pos);return value
  if kind==b':':
   value=self.take(self.number());self.symbols.append(value);return value
  if kind in (b'@',b';'):
   index=self.number();table=self.objects if kind==b'@' else self.symbols
   if not 0<=index<len(table):raise ValueError('Invalid Marshal reference')
   return table[index]
  if kind==b'I':
   value=self.object(depth+1);count=self.number()
   if not 0<=count<=32:raise ValueError('Invalid string metadata count')
   for _ in range(count):self.object(depth+1);self.object(depth+1)
   return value
  if kind==b'[':
   count=self.number()
   if count<0 or count>len(self.data)-self.pos:raise ValueError('Invalid array length')
   value=[];self.objects.append(value)
   value.extend(self.object(depth+1) for _ in range(count));return value
  raise ValueError(f'Unsupported Scripts.rxdata Marshal tag {kind!r} at {self.pos-1}')

def read(data):
 reader=Reader(data)
 if reader.take(3)!=b'\x04\x08[':raise ValueError('Expected Marshal 4.8 script Array')
 count=reader.number()
 reader.objects.append([]) # The outer array occupies object-reference slot zero.
 if not 0<=count<=10000:raise ValueError('Invalid script count')
 entries=[]
 for index in range(count):
  start=reader.pos;value=reader.object()
  if not (isinstance(value,list) and len(value)==3 and isinstance(value[0],int) and isinstance(value[1],bytes) and isinstance(value[2],bytes)):
   raise ValueError(f'Invalid script entry {index}')
  span=reader.string_spans.get(id(value[2]))
  local_span=(span[0]-start,span[1]-start) if span and span[0]>=start else None
  entry=Entry(*value,reader.data[start:reader.pos],local_span);entry.source();entries.append(entry)
 if reader.pos!=len(data):raise ValueError('Trailing script archive data')
 return entries

def write(entries,replacements):
 if any(not isinstance(index,int) or not 0<=index<len(entries) for index in replacements):raise ValueError('Invalid replacement index')
 parts=[b'\x04\x08[',integer(len(entries))]
 for index,entry in enumerate(entries):
  if index not in replacements:parts.append(entry.raw);continue
  if entry.payload_span:
   start,end=entry.payload_span
   parts.append(entry.raw[:start]+string(zlib.compress(replacements[index]))+entry.raw[end:])
  else:raise ValueError('Cannot replace a shared compressed script reference')
 result=b''.join(parts)
 parsed=read(result)
 assert len(parsed)==len(entries)
 for index,(before,after) in enumerate(zip(entries,parsed)):
  if (before.id,before.name)!=(after.id,after.name) or after.source()!=replacements.get(index,before.source()):
   raise ValueError('Script replacement changes a shared Marshal reference')
  if index not in replacements and before.raw!=after.raw:raise ValueError('Untouched script bytes changed')
 return result
