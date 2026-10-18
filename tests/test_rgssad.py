import struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
WORK=Path(__file__).resolve().parents[1]/'build'
from rgssad import Archive
from rgssad_fixture import pack

class ArchiveTests(unittest.TestCase):
 def setUp(self):WORK.mkdir(exist_ok=True)
 def archive(self,directory,blob):
  path=Path(directory)/'Game.rgssad';path.write_bytes(blob);return Archive(path)
 def test_key_sequence_and_every_tail_length(self):
  entries=[(f'Data\\{n}.bin'.encode(),bytes(range(n))) for n in range(0,17)]
  with tempfile.TemporaryDirectory(dir=WORK) as directory:
   archive=self.archive(directory,pack(entries))
   for name,data in entries:self.assertEqual(archive.read(name.lower().replace(b'\\',b'/')),data)
 def test_rejects_malformed_indexes(self):
  malformed=[b'',b'RGSSAD\0\3',b'RGSSAD\0\1\0',b'RGSSAD\0\1'+struct.pack('<I',0x7fffffff^0xdeadcafe),pack([(b'Data\\x',b'a')])[:-1],pack([(b'..\\x',b'a')]),pack([(b'Data/x',b'a'),(b'DATA/X',b'b')])]
  with tempfile.TemporaryDirectory(dir=WORK) as directory:
   for blob in malformed:
    with self.assertRaises(ValueError):self.archive(directory,blob)

if __name__=='__main__':unittest.main()
