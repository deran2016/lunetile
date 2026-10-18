"""Chosen plaintext archive fixture, accepted by the original RGSS104E runtime."""
import struct

def pack(entries):
 key=0xdeadcafe;output=bytearray(b'RGSSAD\0\x01')
 def step(value):return (value*7+3)&0xffffffff
 for name,data in entries:
  output.extend(struct.pack('<I',len(name)^key));key=step(key)
  for byte in name:
   output.append(byte^(key&255));key=step(key)
  output.extend(struct.pack('<I',len(data)^key));key=step(key)
  data_key=key
  for index,byte in enumerate(data):
   output.append(byte^((data_key>>((index%4)*8))&255))
   if index%4==3:data_key=step(data_key)
 return bytes(output)
