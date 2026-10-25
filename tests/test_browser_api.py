import subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUBY=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'

class BrowserAPITests(unittest.TestCase):
 @unittest.skipUnless(RUBY.is_file(),'Pinned Ruby bootstrap required')
 def test_wrapper_validates_and_copies_geometry_and_strings(self):
  source="""
Rect=Struct.new(:x,:y,:width,:height)
module Lunetile
 class Browser
  attr_reader :received
  def __create(*values); @values=values; end
  def __rect; @values.dup; end
  def __set_rect(*values); @values=values; end
  def __navigate(value); @received=value; end
  alias __load_file __navigate
  def __error; [:navigation,7]; end
 end
end
load ARGV.fetch(0)
def rejects(klass)
 begin;yield;raise 'accepted invalid value';rescue klass;end
end
rejects(TypeError) { Lunetile::Browser.new(nil) }
rejects(ArgumentError) { Lunetile::Browser.new(Rect.new(0,0,31,100)) }
rejects(ArgumentError) { Lunetile::Browser.new(Rect.new(0,0,100,4097)) }
rejects(ArgumentError) { Lunetile::Browser.new(Rect.new(0.5,0,100,100)) }
rect=Rect.new(0,0,100,100);view=Lunetile::Browser.new(rect);rect.x=10
raise 'input rect retained' unless view.rect.x==0
copy=view.rect;copy.width=900
raise 'output rect retained' unless view.rect.width==100
rejects(TypeError) { view.navigate(1) }
['',"bad\\0url",'a'*8193].each { |s| rejects(ArgumentError) { view.navigate(s) } }
raise 'chain result' unless view.load_file('Web/한글 파일.html').equal?(view)
raise 'UTF8 conversion' unless view.received.encoding==Encoding::UTF_8
raise 'error detail' unless view.error.code==:navigation && view.error.native_code==7
"""
  result=subprocess.run([str(RUBY),'--disable-gems','-e',source,str(ROOT/'src/runtime/browser.rb')],capture_output=True,text=True,encoding='utf-8',timeout=20)
  self.assertEqual(result.returncode,0,result.stderr)
