use super::*;
use std::sync::{Arc,Mutex,atomic::{AtomicUsize,Ordering}};
pub const APPEARANCES:[&str;3]=["001-Fighter01","002-Fighter02","003-Fighter03"];
pub const NAME_TAKEN:&str="이미 사용 중인 닉네임입니다. 다른 이름을 입력하세요.";
pub fn name_key(value:&str)->String {value.to_ascii_lowercase()}
fn nickname(value:&str)->bool {(2..=12).contains(&value.chars().count())&&value.chars().all(|c|c.is_ascii_alphanumeric()||('\u{ac00}'..='\u{d7a3}').contains(&c))}
const ITERATIONS:u64=600_000;
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Character {pub id:String,pub token:String,pub name:String,pub character:String,#[serde(default)]pub pending:bool}
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
struct Account {schema:u32,username:String,salt:String,password_hash:String,iterations:u64,characters:[Option<Character>;3]}
struct Data {accounts:BTreeMap<String,Account>,active:BTreeSet<String>}
pub struct Accounts {root:PathBuf,max:usize,data:Mutex<Data>,hashing:AtomicUsize}
pub struct Guard {accounts:Arc<Accounts>,pub username:String}
impl Drop for Guard {fn drop(&mut self){if let Ok(mut d)=self.accounts.data.lock(){d.active.remove(&self.username);}}}
fn username(value:&str)->bool {(3..=20).contains(&value.len())&&value.bytes().all(|b|b.is_ascii_lowercase()||b.is_ascii_digit()||b==b'_')
 && !["con","prn","aux","nul"].contains(&value) && !(value.len()==4&&(value.starts_with("com")||value.starts_with("lpt"))&&value.as_bytes()[3].is_ascii_digit())}
fn password(value:&str)->bool {(12..=128).contains(&value.len())&&value.bytes().all(|b|(32..=126).contains(&b))}
fn hex(bytes:&[u8])->String {bytes.iter().map(|b|format!("{b:02x}")).collect()}
fn unhex(s:&str)->Result<Vec<u8>> {if s.len()%2!=0||!s.bytes().all(|b|b.is_ascii_hexdigit()){return Err("Invalid account hash".into());}(0..s.len()).step_by(2).map(|i|u8::from_str_radix(&s[i..i+2],16).map_err(Into::into)).collect()}
fn equal(a:&[u8],b:&[u8])->bool {a.len()==b.len()&&a.iter().zip(b).fold(0u8,|n,(a,b)|n|(a^b))==0}
#[cfg(windows)]
fn derive(password:&str,salt:&[u8],iterations:u64)->Result<Vec<u8>> {
 use std::ffi::c_void;
 #[link(name="bcrypt")]extern "system" {
  fn BCryptOpenAlgorithmProvider(handle:*mut *mut c_void,name:*const u16,provider:*const u16,flags:u32)->i32;
  fn BCryptDeriveKeyPBKDF2(handle:*mut c_void,password:*const u8,password_len:u32,salt:*const u8,salt_len:u32,iterations:u64,out:*mut u8,out_len:u32,flags:u32)->i32;
  fn BCryptCloseAlgorithmProvider(handle:*mut c_void,flags:u32)->i32;
 }
 let mut handle=std::ptr::null_mut();let algorithm:Vec<u16>="SHA256\0".encode_utf16().collect();let mut out=vec![0;32];
 unsafe {
  if BCryptOpenAlgorithmProvider(&mut handle,algorithm.as_ptr(),std::ptr::null(),8)<0{return Err("Password provider unavailable".into());}
  let result=BCryptDeriveKeyPBKDF2(handle,password.as_ptr(),password.len()as u32,salt.as_ptr(),salt.len()as u32,iterations,out.as_mut_ptr(),32,0);
  BCryptCloseAlgorithmProvider(handle,0);if result<0{return Err("Password hashing failed".into());}
 }Ok(out)
}
#[cfg(not(windows))]fn derive(_: &str,_:&[u8],_:u64)->Result<Vec<u8>>{Err("Windows password provider required".into())}
fn save(root:&Path,a:&Account)->Result<()> {
 let path=root.join("accounts").join(format!("{}.json",a.username));let tmp=path.with_extension("json.tmp");
 let mut f=File::create(&tmp)?;serde_json::to_writer_pretty(&mut f,a)?;f.write_all(b"\n")?;f.sync_all()?;drop(f);replace_file(&tmp,&path)?;Ok(())
}
impl Accounts {
 pub fn open(world:&mut World)->Result<Arc<Self>> {
  let root=world.root.clone();fs::create_dir_all(root.join("accounts"))?;let mut accounts=BTreeMap::new();let mut owned=BTreeSet::new();
  for entry in fs::read_dir(root.join("accounts"))? {let path=entry?.path();if path.extension().is_none_or(|s|s!="json"){continue;}
   if fs::metadata(&path)?.len()>32768{return Err("Account file too large".into());}let mut a:Account=load_json(&path)?;
   if a.schema!=1||!username(&a.username)||path.file_stem().and_then(|s|s.to_str())!=Some(&a.username)||a.iterations!=ITERATIONS||a.salt.len()!=32||a.password_hash.len()!=64||unhex(&a.salt)?.len()!=16||unhex(&a.password_hash)?.len()!=32{return Err("Invalid account file".into());}
   let mut repaired=false;
   for c in a.characters.iter_mut().flatten(){if !owned.insert(c.id.clone()){return Err("Character belongs to multiple accounts".into());}
    if !c.pending&&!world.players.contains_key(&c.id){return Err("Owned character file missing; restore players and transactions backup".into());}
    world.provision(c)?;if c.pending{c.pending=false;repaired=true;}
   }
   if repaired{save(&root,&a)?;}
   if accounts.insert(a.username.clone(),a).is_some(){return Err("Duplicate account".into());}
  }
  if accounts.len()>world.config.max_accounts{return Err("Account limit exceeded".into());}
  Ok(Arc::new(Self{root,max:world.config.max_accounts,data:Mutex::new(Data{accounts,active:BTreeSet::new()}),hashing:AtomicUsize::new(0)}))
 }
 fn hash(&self,password:&str,salt:&[u8])->Result<Vec<u8>> {
  if self.hashing.fetch_add(1,Ordering::SeqCst)>=2{self.hashing.fetch_sub(1,Ordering::SeqCst);return Err("인증 요청이 많습니다. 잠시 후 다시 시도하세요.".into());}
  let result=derive(password,salt,ITERATIONS);self.hashing.fetch_sub(1,Ordering::SeqCst);result
 }
 pub fn authenticate(self:&Arc<Self>,name:&str,secret:&str,register:bool)->Result<Guard> {
  if !username(name)||!password(secret){return Err("ID는 소문자/숫자/_ 3~20자(예약 ID 제외), 비밀번호는 영문·숫자·기호 12~128자입니다.".into());}
  let existing=self.data.lock().map_err(|_|"Account lock")?.accounts.get(name).cloned();
  let salt=if register{unhex(&random_token()?[..32])?}else{existing.as_ref().map(|a|unhex(&a.salt)).transpose()?.unwrap_or(vec![0;16])};
  let hashed=self.hash(secret,&salt)?;
  if !register&&existing.as_ref().is_none_or(|a|!unhex(&a.password_hash).is_ok_and(|expected|equal(&hashed,&expected))){return Err("아이디 또는 비밀번호를 확인하세요.".into());}
  let mut d=self.data.lock().map_err(|_|"Account lock")?;
  if register {
   if d.accounts.contains_key(name){return Err("이미 사용 중인 아이디입니다.".into());}
   if d.accounts.len()>=self.max{return Err("계정 생성 한도입니다.".into());}
   let account=Account{schema:1,username:name.into(),salt:hex(&salt),password_hash:hex(&hashed),iterations:ITERATIONS,characters:Default::default()};save(&self.root,&account)?;d.accounts.insert(name.into(),account);
  }
  if !d.active.insert(name.into()){return Err("이미 접속 중인 계정입니다.".into());}
  Ok(Guard{accounts:self.clone(),username:name.into()})
 }
 pub fn owned(&self,id:&str)->Result<bool>{Ok(self.data.lock().map_err(|_|"Account lock")?.accounts.values().any(|a|a.characters.iter().flatten().any(|c|c.id==id)))}
 pub fn characters(&self,name:&str)->Result<[Option<Character>;3]>{Ok(self.data.lock().map_err(|_|"Account lock")?.accounts.get(name).ok_or("Account missing")?.characters.clone())}
 pub fn create(&self,name:&str,slot:usize,appearance:usize,nickname:&str,names:&BTreeSet<String>,capacity:impl Fn()->bool,provision:impl Fn(&Character)->Result<()>)->Result<()> {
  if slot>=3||appearance>=APPEARANCES.len(){return Err("Invalid character slot or appearance".into());}
  if !self::nickname(nickname){return Err("닉네임은 한글·영문·숫자 2~12자로 입력하세요.".into());}
  let mut d=self.data.lock().map_err(|_|"Account lock")?;let mut a=d.accounts.get(name).ok_or("Account missing")?.clone();
  if let Some(c)=a.characters[slot].clone(){provision(&c)?;if c.pending{a.characters[slot].as_mut().unwrap().pending=false;save(&self.root,&a)?;d.accounts.insert(name.into(),a);}return Ok(());}
  if !capacity(){return Err("서버 캐릭터 생성 한도입니다.".into());}
  if d.accounts.values().flat_map(|a|a.characters.iter().flatten()).any(|c|name_key(&c.name)==name_key(nickname))||names.iter().any(|n|name_key(n)==name_key(nickname)){return Err(NAME_TAKEN.into());}
  let token=random_token()?;let c=Character{id:format!("p_{}",&token[..24]),token,name:nickname.into(),character:APPEARANCES[appearance].into(),pending:true};
  let previous=a.clone();a.characters[slot]=Some(c.clone());
  // Reserve ownership durably first; startup completes a missing initial player after a crash.
  save(&self.root,&a)?;d.accounts.insert(name.into(),a.clone());
  let result=provision(&c);
  if result.is_ok(){a.characters[slot].as_mut().unwrap().pending=false;save(&self.root,&a)?;d.accounts.insert(name.into(),a);}
  else if result.as_ref().is_err_and(|e|e.to_string()=="Character limit reached"||e.to_string()==NAME_TAKEN){save(&self.root,&previous)?;d.accounts.insert(name.into(),previous);}result
 }
 pub fn claim(&self,name:&str,c:Character)->Result<()> {
  let mut d=self.data.lock().map_err(|_|"Account lock")?;
  if let Some(owner)=d.accounts.values().find(|a|a.characters.iter().flatten().any(|p|p.id==c.id)){return if owner.username==name{Ok(())}else{Err("이미 다른 계정에 연결된 캐릭터입니다.".into())};}
  let mut a=d.accounts.get(name).ok_or("Account missing")?.clone();let slot=a.characters.iter().position(Option::is_none).ok_or("빈 캐릭터 슬롯이 없습니다.")?;
  a.characters[slot]=Some(c);save(&self.root,&a)?;d.accounts.insert(name.into(),a);Ok(())
 }
}

#[cfg(test)]
mod tests {
 use super::*;
 fn fixture()->World {
  let source=PathBuf::from(env!("CARGO_MANIFEST_DIR"));let root=source.join("target/test-data").join(format!("accounts-{}-{}",std::process::id(),std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));fs::create_dir_all(root.join("data")).unwrap();
  for n in ["server","maps","items","npcs","growth","skills","monsters","progression","services","particles"]{fs::copy(source.join(format!("data/{n}.json")),root.join(format!("data/{n}.json"))).unwrap();}World::load(&root).unwrap()
 }
 #[test]fn windows_pbkdf2_matches_sha256_vector(){assert_eq!(hex(&derive("password",b"salt",1).unwrap()),"120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b");}
 #[test]fn registration_hashes_password_and_rejects_duplicate_session_and_wrong_password(){
  let mut w=fixture();let a=Accounts::open(&mut w).unwrap();let secret="Only_a_test_1234";let g=a.authenticate("tester",secret,true).unwrap();
  assert!(a.authenticate("tester",secret,false).err().unwrap().to_string().contains("접속"));
  drop(g);assert!(a.authenticate("tester","Wrong_password_1",false).is_err());drop(a.authenticate("tester",secret,false).unwrap());
  assert!(a.authenticate("tester",secret,true).is_err());assert!(a.authenticate("../bad",secret,true).is_err());
  for reserved in ["con","prn","aux","nul","com1","lpt9"]{assert!(a.authenticate(reserved,secret,true).is_err());}
  let bytes=fs::read_to_string(w.root.join("accounts/tester.json")).unwrap();assert!(!bytes.contains(secret));assert!(bytes.contains("600000"));
 }
 #[test]fn reserved_creation_recovers_after_interruption_and_slots_are_idempotent(){
  let mut w=fixture();let a=Accounts::open(&mut w).unwrap();drop(a.authenticate("tester","Only_a_test_1234",true).unwrap());
  assert!(a.create("tester",0,2,"새모험가",&BTreeSet::new(),||true,|_|Err("Injected stop before player commit".into())).is_err());
  let c=a.characters("tester").unwrap()[0].clone().unwrap();assert!(!w.players.contains_key(&c.id));drop(a);
  let a=Accounts::open(&mut w).unwrap();let p=&w.players[&c.id];assert_eq!(p.character,APPEARANCES[2]);assert_eq!(p.name,"새모험가");assert_eq!(p.level,1);
  a.create("tester",0,0,"새모험가",&BTreeSet::new(),||false,|c|{assert_eq!(c.id,p.id);Ok(())}).unwrap();
  assert!(a.create("tester",3,0,"새모험가",&BTreeSet::new(),||true,|_|Ok(())).is_err());assert!(a.create("tester",1,9,"새모험가",&BTreeSet::new(),||true,|_|Ok(())).is_err());
 }
 #[test]fn claim_preserves_legacy_player_and_prevents_other_account_ownership(){
  let mut w=fixture();let(id,token)=w.login(Command::Register{protocol:PROTOCOL,name:"기존 캐릭터".into()}).unwrap();
  w.players.get_mut(&id).unwrap().character="004-Fighter04".into();save_player(&w.root,&w.players[&id]).unwrap();let before=fs::read(w.root.join(format!("players/{id}.json"))).unwrap();
  let a=Accounts::open(&mut w).unwrap();for n in ["first","second"]{drop(a.authenticate(n,"Only_a_test_1234",true).unwrap());}
  let c=Character{id:id.clone(),token,name:w.players[&id].name.clone(),character:w.players[&id].character.clone(),pending:false};a.claim("first",c.clone()).unwrap();a.claim("first",c.clone()).unwrap();assert!(a.claim("second",c).is_err());
  assert!(a.owned(&id).unwrap());assert_eq!(fs::read(w.root.join(format!("players/{id}.json"))).unwrap(),before);
  drop(a);let a=Accounts::open(&mut w).unwrap();assert_eq!(a.characters("first").unwrap()[0].as_ref().unwrap().character,"004-Fighter04");assert_eq!(fs::read(w.root.join(format!("players/{id}.json"))).unwrap(),before);
 }
 #[test]fn failed_account_replace_never_publishes_and_invalid_unicode_hash_is_rejected(){
  let mut w=fixture();let a=Accounts::open(&mut w).unwrap();fs::create_dir(w.root.join("accounts/tester.json.tmp")).unwrap();assert!(a.authenticate("tester","Only_a_test_1234",true).is_err());assert!(!a.data.lock().unwrap().accounts.contains_key("tester"));
  assert!(unhex("가나다라").is_err());
 }
 #[test]fn missing_established_character_is_never_reset_to_a_new_player(){
  let mut w=fixture();let a=Accounts::open(&mut w).unwrap();drop(a.authenticate("tester","Only_a_test_1234",true).unwrap());
  let world=std::cell::RefCell::new(&mut w);a.create("tester",0,0,"새모험가",&BTreeSet::new(),||true,|c|world.borrow_mut().provision(c)).unwrap();drop(world);
  let c=a.characters("tester").unwrap()[0].clone().unwrap();assert!(!c.pending);fs::remove_file(w.root.join(format!("players/{}.json",c.id))).unwrap();w.players.remove(&c.id);drop(a);
  assert!(Accounts::open(&mut w).err().unwrap().to_string().contains("restore"));assert!(!w.players.contains_key(&c.id));
 }
 #[test]fn nicknames_validate_and_reject_existing_pending_and_case_equivalent_names(){
  for n in ["한글", "Ab12"]{assert!(nickname(n));}assert!(nickname(&"가".repeat(12)));
  for n in ["", "가", "가나다라마바사아자차카타파", " 앞뒤", "띄어 쓰기", "../bad", "이름_", "😀😀", "가나"]{assert!(!nickname(n));}
  let mut w=fixture();let a=Accounts::open(&mut w).unwrap();for n in ["first","second"]{drop(a.authenticate(n,"Only_a_test_1234",true).unwrap());}
  assert!(a.create("first",0,0,"예약이름",&BTreeSet::new(),||true,|_|Err("Injected stop".into())).is_err());
  assert_eq!(a.create("second",0,1,"예약이름",&BTreeSet::new(),||true,|_|panic!("duplicate provisioned")).err().unwrap().to_string(),NAME_TAKEN);
  assert!(a.create("second",0,1,"legacy",&BTreeSet::from(["Legacy".into()]),||true,|_|panic!("legacy duplicate provisioned")).is_err());
  assert!(a.create("second",0,3,"올바른이름",&BTreeSet::new(),||true,|_|Ok(())).is_err());
  assert!(a.create("second",0,0,"잘못된 이름",&BTreeSet::new(),||true,|_|Ok(())).is_err());
  assert!(a.characters("second").unwrap().iter().all(Option::is_none));
 }
 #[test]fn named_characters_and_all_three_appearances_survive_recovery(){
  let mut w=fixture();let a=Accounts::open(&mut w).unwrap();drop(a.authenticate("tester","Only_a_test_1234",true).unwrap());
  let world=std::cell::RefCell::new(&mut w);
  for (i,n) in ["검사하나","마법둘","Archer3"].iter().enumerate(){a.create("tester",i,i,n,&BTreeSet::new(),||true,|c|world.borrow_mut().provision(c)).unwrap();}
  drop(world);drop(a);let a=Accounts::open(&mut w).unwrap();
  for (i,c) in a.characters("tester").unwrap().iter().flatten().enumerate(){assert_eq!(c.character,APPEARANCES[i]);assert_eq!(w.players[&c.id].name,c.name);assert!(!c.pending);}
 }
 #[test]fn simultaneous_case_equivalent_creations_have_one_winner(){
  let mut w=fixture();let a=Accounts::open(&mut w).unwrap();for n in ["first","second"]{drop(a.authenticate(n,"Only_a_test_1234",true).unwrap());}
  let barrier=Arc::new(std::sync::Barrier::new(2));let count=Arc::new(AtomicUsize::new(0));
  let jobs:Vec<_>=[("first","Hero123"),("second","hERO123")].into_iter().map(|(account,n)|{let a=a.clone();let b=barrier.clone();let count=count.clone();std::thread::spawn(move||{b.wait();a.create(account,0,1,n,&BTreeSet::new(),||true,|_|{count.fetch_add(1,Ordering::SeqCst);Ok(())}).is_ok()})}).collect();
  assert_eq!(jobs.into_iter().map(|j|j.join().unwrap()as usize).sum::<usize>(),1);assert_eq!(count.load(Ordering::SeqCst),1);
 }
 #[test]fn definitive_world_name_conflict_releases_reserved_slot(){
  let mut w=fixture();let a=Accounts::open(&mut w).unwrap();drop(a.authenticate("tester","Only_a_test_1234",true).unwrap());
  assert!(a.create("tester",0,0,"이미존재",&BTreeSet::new(),||true,|_|Err(NAME_TAKEN.into())).is_err());
  assert!(a.characters("tester").unwrap().iter().all(Option::is_none));drop(a);assert!(Accounts::open(&mut w).is_ok());
 }
}
