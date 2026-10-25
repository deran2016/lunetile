import struct,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class MMOArtAssetTests(unittest.TestCase):
 def test_portal_is_rgba_png_with_four_by_four_frames_and_generation_record(self):
  asset=ROOT/'example/assets/Graphics/Characters/Lunetile_Portal.png';raw=asset.read_bytes()
  self.assertEqual(raw[:8],b'\x89PNG\r\n\x1a\n')
  w,h,depth,kind=struct.unpack('>IIBB',raw[16:26])
  self.assertEqual((w,h,depth,kind),(1254,1254,8,6))
  self.assertGreaterEqual(w//4,32);self.assertEqual(w//4,h//4)
  record=(ROOT/'example/assets/ART_ASSETS.md').read_text(encoding='utf-8')
  self.assertIn('built-in',record);self.assertIn('Generation prompt',record)
