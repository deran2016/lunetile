import subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUBY=ROOT/'build/runtime-native/bin/Release/rgssxp-ruby.exe'
@unittest.skipUnless(RUBY.exists(),'Build the Ruby helper first')
class AccountClientTests(unittest.TestCase):
 def ruby(self,source):
  r=subprocess.run([str(RUBY),'--disable-gems','-'],input=source,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=20)
  self.assertEqual(r.returncode,0,r.stdout+r.stderr)
 def test_creation_name_composition_appearance_duplicate_retry_and_success(self):
  self.ruby("""# encoding: UTF-8
class Color;def initialize(*);end;end
module Lunetile;module UIInput
 class << self;attr_accessor :value,:composition,:keys;end
 def self.text_input=(v);self.composition='' unless v;end
 def self.text;v=value||'';self.value='';v;end
 def self.key_trigger?(k);(keys||[]).include?(k);end
 def self.text_submit?;key_trigger?(:enter);end
 def self.composing?;!composition.to_s.empty?;end
 def self.mouse_trigger?(_);false;end
end;end
load 'example/client/mmo_entry.rb'
c=Object.new;class << c;attr_accessor :account_revision,:account_response_kind,:account_error;end
c.account_revision=0;c.define_singleton_method(:update){};c.define_singleton_method(:state){nil};c.define_singleton_method(:account){{'username'=>'tester'}}
sent=[];c.define_singleton_method(:send_message){|m|sent<<m}
s=LunetileMMO::Entry.allocate;{connection:c,revision:0,mode: :characters,appearance:0}.each{|k,v|s.instance_variable_set("@#{k}",v)}
s.define_singleton_method(:layout){};s.define_singleton_method(:draw){}
s.action([:create,1]);raise unless sent.empty? && s.instance_variable_get(:@mode)==:create
s.action([:appearance,2]);u=Lunetile::UIInput;u.value='한글';s.update;u.composition='이름';s.action(:confirm_create)
raise unless sent==[{'type'=>'character_create','slot'=>1,'appearance'=>2,'name'=>'한글이름'}]
s.action(:confirm_create);raise unless sent.size==1
c.account_revision=1;c.account_response_kind='character_create';c.account_error='이미 사용 중';s.update
raise unless s.instance_variable_get(:@mode)==:create && s.instance_variable_get(:@status).include?('사용') && s.instance_variable_get(:@nickname)=='한글이름'
s.instance_variable_set(:@nickname,'공백 이름');s.action(:confirm_create);raise unless sent.size==1
s.instance_variable_set(:@nickname,'새이름');u.keys=[:enter];s.update;raise unless sent.last['name']=='새이름' && sent.size==2
u.keys=[];c.account_revision=2;c.account_error=nil;s.update
raise unless s.instance_variable_get(:@mode)==:characters && s.instance_variable_get(:@nickname)==''
s.action([:create,0]);s.action(:cancel_create);raise unless s.instance_variable_get(:@mode)==:characters && sent.size==2
""")
 def test_composition_commit_submits_once_even_when_general_enter_is_suppressed(self):
  self.ruby("""# encoding: UTF-8
module Lunetile;module UIInput
 def self.text_input=(_);end
 def self.mouse_press_position;nil;end
 def self.mouse_position;nil;end
 def self.key_trigger?(_);false;end
 def self.composing?;true;end
 def self.text;'글';end
 def self.text_submit?;true;end
end;end
load 'example/client/mmo_chat.rb'
s=LunetileMMO::Scene.allocate;sent=[];c=Object.new;c.define_singleton_method(:send_message){|m|sent<<m}
s.instance_variable_set(:@connection,c);s.instance_variable_set(:@chat_open,true);s.instance_variable_set(:@draft,'한')
s.define_singleton_method(:handle_chat_scroll){false};s.define_singleton_method(:chat_focus){|v|@chat_open=v}
raise unless s.handle_chat && sent==[{'type'=>'chat','text'=>'한글'}]
raise if s.handle_chat;raise unless sent.size==1 && s.instance_variable_get(:@draft)==''
""")
 def test_login_keyboard_focus_validation_and_no_nickname_field(self):
  self.ruby("""# encoding: UTF-8
class Color;def initialize(*);end;end
module Lunetile;module UIInput
 class << self;attr_accessor :typing,:value,:keys;end
 def self.text_input=(v);self.typing=v;end
 def self.ime_open?;false;end
 def self.ime_open=(_);end
 def self.text;value||'';end
 def self.key_trigger?(k);(keys||[]).include?(k);end
 def self.text_submit?;key_trigger?(:enter);end
 def self.mouse_trigger?(_);false;end
end;end
module LunetileMMO;PROTOCOL=11;end
load 'example/client/mmo_entry.rb'
s=LunetileMMO::Entry.allocate;c=Object.new;sent=[]
c.define_singleton_method(:update){};c.define_singleton_method(:state){nil};c.define_singleton_method(:account_revision){0};c.define_singleton_method(:send_message){|m|sent<<m}
s.instance_variable_set(:@connection,c);s.instance_variable_set(:@revision,0);s.instance_variable_set(:@fields,['','','']);s.instance_variable_set(:@field,0);s.instance_variable_set(:@mode,:login);s.define_singleton_method(:draw){}
u=Lunetile::UIInput;u.value='My_ID!?';u.keys=[:tab];s.update;raise unless s.instance_variable_get(:@field)==1 && s.instance_variable_get(:@fields)[0]=='my_id'
u.value='Test_only_password_1';u.keys=[:enter];s.update
raise unless sent==[{'type'=>'account_login','protocol'=>11,'username'=>'my_id','password'=>'Test_only_password_1'}]
s.instance_variable_set(:@mode,:register);s.instance_variable_set(:@pending,nil);s.instance_variable_set(:@fields,['my_id','Test_only_password_1','mismatch']);s.authenticate
raise unless sent.size==1 && s.instance_variable_get(:@status).include?('일치')
""")
 def test_owned_character_uses_separate_profile_and_keeps_legacy_quickslots(self):
  self.ruby("""# encoding: UTF-8
require 'json';load 'example/client/mmo_network.rb'
dir=File.expand_path("build/account-profile-#{Process.pid}");Dir.mkdir(dir);old=Dir.pwd
begin
 Dir.chdir(dir);Dir.mkdir('ClientProfile');id='p_0123456789abcdef01234567';legacy='ClientProfile/legacy.json';File.write(legacy,JSON.generate({'id'=>id,'token'=>'old'}));before=File.binread(legacy)
 quick={'id'=>id,'slots'=>['skill:basic',nil,nil,nil,nil,nil,nil,nil]};File.write('ClientProfile/legacy.quicks.json',JSON.generate(quick));original_quick=File.binread('ClientProfile/legacy.quicks.json')
 c=LunetileMMO::Connection.allocate
 {lobby:true,profile_path:legacy,legacy_profile_path:legacy,credentials:{'id'=>id,'token'=>'old'},states:[],account_requests:['account_login'],account_revision:0}.each{|k,v|c.instance_variable_set("@#{k}",v)}
 message={'type'=>'account','protocol'=>11,'username'=>'tester','characters'=>[nil,nil,nil],'appearances'=>%w[001-Fighter01 002-Fighter02 003-Fighter03]}
 begin;c.receive(message.merge('characters'=>[{'id'=>'../unsafe'}]));raise 'bad character list accepted';rescue RuntimeError=>e;raise unless e.message.include?('형식');end
 c.receive(message);raise if c.state;raise unless c.account_revision==1
 state={'type'=>'state','move_ack'=>{'seq'=>0,'accepted'=>false},'self'=>{'hp'=>70}};catalog={'items'=>[],'skills'=>[],'progression'=>{},'services'=>{},'particle_presets'=>[]}
 c.receive({'type'=>'welcome','protocol'=>11,'id'=>id,'token'=>'new','catalog'=>catalog,'state'=>state})
 raise unless File.binread(legacy)==before && File.binread('ClientProfile/legacy.quicks.json')==original_quick
 raise unless File.binread("ClientProfile/c_#{id}.quicks.json")==original_quick && c.quickslots==quick['slots']
ensure
 Dir.chdir(old);Dir.children(File.join(dir,'ClientProfile')).each{|n|File.delete(File.join(dir,'ClientProfile',n))};Dir.rmdir(File.join(dir,'ClientProfile'));Dir.rmdir(dir)
end
""")
