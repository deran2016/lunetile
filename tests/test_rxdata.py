import sys,unittest,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from rxdata import Reader,Entry,integer,read,write,string
from migrate_project import transform,MigrationError

class RxdataTests(unittest.TestCase):
 def test_signed_integer_boundaries(self):
  for value in [-2147483648,-65537,-65536,-257,-256,-255,-129,-128,-124,-123,-5,-4,-1,0,1,122,123,127,128,255,256,65535,2147483647]:
   reader=Reader(integer(value));self.assertEqual(reader.number(),value);self.assertEqual(reader.pos,len(reader.data))
 def test_preserves_untouched_entry_bytes(self):
  raw=b'\x04\x08['+integer(2)
  for ident,name,body in [(-123,b'first',b'puts 1'),(123,b'second',b'puts 2')]:
   raw+=b'['+integer(3)+b'i'+integer(ident)+string(name)+string(zlib.compress(body,1))
  entries=read(raw);rebuilt=write(entries,{1:b'puts 3'})
  self.assertEqual(write(entries,{}),raw)
  parsed=read(rebuilt);self.assertEqual(parsed[0].raw,entries[0].raw)
  self.assertEqual(parsed[1].source(),b'puts 3');self.assertEqual(parsed[1].id,123)
 def test_rejects_truncated_and_unexpected_objects(self):
  for raw in [b'',b'\x04\x08[\x06',b'\x04\x08[\xff',b'\x04\x08[\x06@\x00',b'\x04\x08[\x00extra']:
   with self.assertRaises(ValueError):read(raw)
 def test_rejects_zlib_trailer_and_truncation(self):
  for payload in [zlib.compress(b'x')+b'extra',zlib.compress(b'x')[:-1],b'raw Ruby']:
   with self.assertRaises(ValueError):Entry(1,b'name',payload,b'').source()
 def test_unknown_script_is_not_rewritten(self):
  with self.assertRaises(MigrationError):transform([Entry(1,b'Main',zlib.compress(b'custom code'),b'')])

if __name__=='__main__':unittest.main()
