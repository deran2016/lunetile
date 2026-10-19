import subprocess,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUBY=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'

@unittest.skipUnless(RUBY.exists(),'Build the pinned Ruby helper first')
class NetworkAPITests(unittest.TestCase):
 def ruby(self,source):
  setup="module Lunetile; module HTTP\n def self.__start(*args); @arguments=args; Object.new; end\n def self.arguments; @arguments; end\nend\nmodule TCP; def self.__connect(*); raise 'Unexpected native call'; end; end; end\nload 'src/runtime/network.rb'\n"
  result=subprocess.run([str(RUBY),'--disable-gems','-e',setup+source],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=10)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)

 def test_json_body_header_and_null_are_not_confused_with_omission(self):
  self.ruby("Lunetile::HTTP.request(:post,'https://example.test/',json:nil)\na=Lunetile::HTTP.arguments\nraise unless a[0]=='POST' && a[2].include?('application/json') && a[3]=='null'\nLunetile::HTTP.request(:post,'https://example.test/',body: \"\\x00\\xff\".b)\nraise unless Lunetile::HTTP.arguments[3].bytes==[0,255]")

 def test_invalid_headers_and_options_are_rejected(self):
  self.ruby("bad=[{body:'x',json:{}},{headers:{'X-Test'=>\"x\\r\\nInjected: y\"}},{headers:{'Host'=>'evil'}},{headers:{'X'=>'a','x'=>'b'}},{headers:{'bad name'=>'x'}},{body:'x'*(1024*1024+1)}]\nbad.each do |options|\n begin; Lunetile::HTTP.request(:get,'https://example.test/',**options); raise 'accepted bad input'; rescue ArgumentError; end\nend\nbegin; Lunetile::HTTP.request(:trace,'https://example.test/'); raise; rescue ArgumentError; end")

 def test_response_preserves_headers_and_binary_body(self):
  self.ruby("body=\"\\x00\\xff\".b\nr=Lunetile::HTTP::Response.new(201,\"HTTP/1.1 201 Created\\r\\nSet-Cookie: a=1\\r\\nSet-Cookie: b=2\\r\\nX-Empty: \\r\\n\",body)\nraise unless r.status==201 && r.headers['set-cookie']==['a=1','b=2'] && r.headers['x-empty']==[''] && r.body.bytes==[0,255] && r.headers.frozen? && r.body.frozen?")

 def test_json_response_uses_strict_non_restoring_parse(self):
  self.ruby("['NaN',\"\\xff\".b,'['*101+'0'+']'*101].each do |body|\n begin; Lunetile::HTTP::Response.new(200,'',body).json; raise 'accepted bad JSON'; rescue JSON::ParserError,JSON::NestingError; end\nend\nr=Lunetile::HTTP::Response.new(200,'','{\"json_class\":\"Object\",\"x\":1}'.b)\nraise unless r.json=={'json_class'=>'Object','x'=>1}")

 def test_tcp_rejects_invalid_address_port_and_tls(self):
  self.ruby("module Lunetile::TCP; def self.__connect(*); raise 'native API should not run'; end; end\n[['',1,true],['bad/host',1,true],['localhost',0,true],['localhost',65536,true],['localhost',1,nil]].each do |host,port,tls|\n begin; Lunetile::TCP.connect(host,port,tls:tls); raise 'accepted bad TCP input'; rescue ArgumentError; end\nend")

 def test_json_parse_failure_does_not_expose_response_in_exception_chain(self):
  self.ruby("begin\nLunetile::HTTP::Response.new(200,'','LUNETILE-SECRET-invalid-json'.b).json\nraise 'accepted invalid JSON'\nrescue JSON::ParserError => error\nraise unless error.message=='Invalid JSON response' && error.cause.nil?\nend")
