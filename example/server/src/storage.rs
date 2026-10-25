use super::*;
use std::{cell::RefCell,collections::VecDeque,sync::{mpsc,Arc,Mutex},thread};
const LIMIT:u64=64*1024*1024;
const RECORD_LIMIT:usize=16*1024*1024;
const END:[u8;4]=*b"MMO9";
thread_local! {static CAPTURE:RefCell<Option<(PathBuf,Vec<Vec<Player>>)>>=const{RefCell::new(None)};}
pub fn begin(root:&Path){CAPTURE.with(|c|{assert!(c.borrow().is_none());*c.borrow_mut()=Some((root.into(),Vec::new()));});}
pub fn take()->Vec<Vec<Player>>{CAPTURE.with(|c|c.borrow_mut().take().expect("capture scope").1)}
pub fn stage(root:&Path,players:&[Player])->bool {
 CAPTURE.with(|c|{let mut c=c.borrow_mut();if let Some((path,updates))=c.as_mut(){assert_eq!(path,root);updates.push(players.to_vec());true}else{false}})
}
fn crc(bytes:&[u8])->u32 {let mut c=!0u32;for b in bytes{c^=u32::from(*b);for _ in 0..8{c=(c>>1)^(0xedb88320u32.wrapping_mul(c&1));}}!c}
fn encode(seq:u64,players:&[Player])->Result<Vec<u8>> {
 let body=serde_json::to_vec(players)?;if body.len()>RECORD_LIMIT{return Err("WAL record too large".into());}
 let mut out=Vec::with_capacity(body.len()+20);out.extend(seq.to_le_bytes());out.extend((body.len()as u32).to_le_bytes());out.extend(crc(&body).to_le_bytes());out.extend(body);out.extend(END);Ok(out)
}
fn checkpoint_seq(root:&Path)->Result<u64> {let p=root.join("transactions/checkpoint.json");if p.exists(){Ok(load_json::<u64>(&p)?)}else{Ok(0)}}
fn marker(root:&Path,seq:u64)->Result<()> {
 let path=root.join("transactions/checkpoint.json");let tmp=path.with_extension("tmp");let mut f=File::create(&tmp)?;serde_json::to_writer(&mut f,&seq)?;f.sync_all()?;drop(f);replace_file(&tmp,&path)?;Ok(())
}
fn valid(players:&[Player])->bool {
 !players.is_empty()&&players.len()<=64&&players.iter().all(|p|valid_id(&p.id)&&(2..=3).contains(&p.schema)&&p.token.len()==64&&p.token.bytes().all(|b|b.is_ascii_hexdigit())&&p.level>0&&p.hp<=p.max_hp&&p.mp<=p.max_mp)
}
pub fn recover(root:&Path)->Result<()> {
 let path=root.join("transactions/active.wal");if !path.exists(){return Ok(());}
 if fs::metadata(&path)?.len()>LIMIT+RECORD_LIMIT as u64{return Err("WAL exceeds recovery limit".into());}
 let checkpoint=checkpoint_seq(root)?;let bytes=fs::read(&path)?;
 let (mut at,mut previous,mut latest)=(0,None,checkpoint);let mut updates=BTreeMap::new();
 while at<bytes.len() {
  if bytes.len()-at<16{break;}
  let seq=u64::from_le_bytes(bytes[at..at+8].try_into()?);let len=u32::from_le_bytes(bytes[at+8..at+12].try_into()?)as usize;
  let checksum=u32::from_le_bytes(bytes[at+12..at+16].try_into()?);
  if len>RECORD_LIMIT{return Err("Invalid WAL record length".into());}
  if bytes.len()-at<20+len{break;}
  let body=&bytes[at+16..at+16+len];
  if bytes[at+16+len..at+20+len]!=END||crc(body)!=checksum{return Err("WAL checksum/marker damaged; restore backup".into());}
  if seq==0||previous.is_some_and(|p|seq!=p+1)||(previous.is_none()&&seq>checkpoint.saturating_add(1)){return Err("WAL sequence gap".into());}
  previous=Some(seq);let players:Vec<Player>=serde_json::from_slice(body)?;if !valid(&players){return Err("Invalid WAL player state".into());}
  if seq>checkpoint{for p in players{updates.insert(p.id.clone(),p);}latest=seq;}
  at+=20+len;
 }
 for p in updates.values(){super::save_player_now(root,p)?;}
 marker(root,latest)?;
 // The checkpoint is durable before covered or incomplete trailing records disappear.
 let tmp=path.with_extension("tmp");let f=File::create(&tmp)?;f.sync_all()?;drop(f);replace_file(&tmp,&path)?;
 Ok(())
}
enum Job {Commit(Vec<Vec<Player>>,mpsc::SyncSender<std::result::Result<(),String>>),Checkpoint(u64),Stop}
#[derive(Default)]
struct Pending {seq:u64,players:BTreeMap<String,Player>}
pub struct Store {send:mpsc::SyncSender<Job>,stop:mpsc::SyncSender<()>,writer:Option<thread::JoinHandle<std::result::Result<(),String>>>,checkpointer:Option<thread::JoinHandle<std::result::Result<(),String>>>}
impl Store {
 pub fn start(root:&Path)->Result<Self> {
  Self::open(root,0)
 }
 fn open(root:&Path,fault:u8)->Result<Self> {
  fs::create_dir_all(root.join("transactions"))?;let seq=checkpoint_seq(root)?;let root=root.to_path_buf();
  let (send,receive)=mpsc::sync_channel(128);let (stop,end)=mpsc::sync_channel(1);let pending=Arc::new(Mutex::new(Pending::default()));
  let cp_root=root.clone();let cp_pending=pending.clone();let cp_send=send.clone();
  let checkpointer=thread::Builder::new().name("json-checkpoint".into()).spawn(move||{
   loop {
    let stopping=!matches!(end.recv_timeout(Duration::from_secs(1)),Err(mpsc::RecvTimeoutError::Timeout));
    let mut work={let mut p=cp_pending.lock().map_err(|_|"checkpoint lock")?;std::mem::take(&mut *p)};
    if !work.players.is_empty(){
     let began=Instant::now();let result=(||->Result<()>{
      let players:Vec<_>=work.players.values().collect();
      if fault==4{if let Some(p)=players.first(){super::save_player_now(&cp_root,p)?;}return Err("Injected partial JSON checkpoint failure".into());}
      thread::scope(|scope|->Result<()>{let mut jobs=Vec::new();for chunk in players.chunks(players.len().div_ceil(8).max(1)){let root=&cp_root;jobs.push(scope.spawn(move||->Result<()>{for p in chunk{super::save_player_now(root,p)?;}Ok(())}));}for job in jobs{job.join().map_err(|_|"checkpoint worker panicked")??;}Ok(())})?;
      marker(&cp_root,work.seq)?;Ok(())
     })();metrics::elapsed("json_checkpoint",began);
     if let Err(e)=result {
      metrics::record("checkpoint_errors",1);eprintln!("JSON checkpoint delayed; WAL retained: {e}");
      let mut p=cp_pending.lock().map_err(|_|"checkpoint lock")?;p.seq=p.seq.max(work.seq);for(id,player)in std::mem::take(&mut work.players){p.players.entry(id).or_insert(player);}
      if stopping{return Err(format!("Checkpoint failed; use --recover-only: {e}"));}
     }else{cp_send.send(Job::Checkpoint(work.seq)).map_err(|_|"WAL worker unavailable")?;}
    }
    if stopping{return Ok(());}
   }
  })?;
  let writer=thread::Builder::new().name("durable-wal".into()).spawn(move||{
   let result=(||->Result<()>{
    let path=root.join("transactions/active.wal");let mut file=OpenOptions::new().create(true).append(true).open(&path)?;
    let mut sequence=seq;let mut retained:VecDeque<(u64,Vec<u8>)>=VecDeque::new();let mut size=if fault==6{LIMIT}else{file.metadata()?.len()};let mut failed=false;
    for job in receive {match job {
     Job::Stop=>break,
     Job::Checkpoint(done)=>{
      let began=Instant::now();while retained.front().is_some_and(|(seq,_)|*seq<=done){retained.pop_front();}
      drop(file);
      let compact=(||->Result<()>{let tmp=path.with_extension("tmp");let mut next=File::create(&tmp)?;for(_,bytes)in &retained{next.write_all(bytes)?;}next.sync_all()?;drop(next);if fault==5{return Err("Injected compaction failure".into());}replace_file(&tmp,&path)?;Ok(())})();
      // Covered records are already durable in JSON; a failed replacement must retain the WAL.
      if let Err(e)=compact{metrics::record("compaction_errors",1);eprintln!("WAL compaction delayed; journal retained: {e}");}
      file=OpenOptions::new().append(true).open(&path)?;size=file.metadata()?.len();metrics::gauge("wal_bytes",size);metrics::elapsed("wal_compact",began);
     }
     Job::Commit(records,reply)=>{
      let began=Instant::now();let result=(||->Result<()>{
       if failed{return Err("WAL unavailable; restart with --recover-only".into());}
       let mut encoded=Vec::new();let mut next_seq=sequence;
       for players in &records {if !valid(players){return Err("Invalid WAL transaction".into());}next_seq+=1;encoded.push((next_seq,encode(next_seq,players)?));}
       let extra:usize=encoded.iter().map(|(_,b)|b.len()).sum();if size+extra as u64>LIMIT{return Err("WAL reached 64 MiB; recover checkpoint before accepting changes".into());}
       if fault==1{return Err("Injected WAL append failure".into());}
       for(_,bytes)in &encoded{file.write_all(bytes)?;}
       if fault==2{return Err("Injected WAL sync failure".into());}
       let sync=Instant::now();file.sync_all()?;metrics::elapsed("wal_sync",sync);
       if fault==3{return Err("Injected failure after sync before acknowledgement".into());}
       size+=extra as u64;metrics::gauge("wal_bytes",size);sequence=next_seq;retained.extend(encoded);
       let mut p=pending.lock().map_err(|_|"checkpoint lock")?;p.seq=sequence;for record in records{for player in record{p.players.insert(player.id.clone(),player);}}metrics::gauge("dirty_players",p.players.len()as u64);
       Ok(())
      })();metrics::elapsed("wal_commit",began);if result.is_err(){failed=true;metrics::record("wal_errors",1);}
      let _=reply.send(result.map_err(|e|e.to_string()));
     }
    }}Ok(())
   })();if let Err(e)=&result{eprintln!("WAL worker stopped: {e}");}result.map_err(|e|e.to_string())
  })?;
  Ok(Self{send,stop,writer:Some(writer),checkpointer:Some(checkpointer)})
 }
 pub fn commit(&self,records:Vec<Vec<Player>>)->Result<()> {
  if records.is_empty(){return Ok(());}
  let (send,receive)=mpsc::sync_channel(1);self.send.send(Job::Commit(records,send))?;receive.recv()?.map_err(Into::into)
 }
 pub fn finish(mut self)->Result<()> {
  let _=self.stop.send(());let checked=self.checkpointer.take().unwrap().join().map_err(|_|"checkpoint panicked")?;
  let _=self.send.send(Job::Stop);let written=self.writer.take().unwrap().join().map_err(|_|"WAL panicked")?;
  checked?;written?;Ok(())
 }
}
impl Drop for Store {fn drop(&mut self){let _=self.stop.try_send(());if self.writer.is_some(){let _=self.send.try_send(Job::Stop);}}}

#[cfg(test)]
mod tests {
 use super::*;
 #[test]fn crc_matches_standard_vector(){assert_eq!(crc(b"123456789"),0xcbf43926);}
 fn fixture()->(World,String,String){
  let source=PathBuf::from(env!("CARGO_MANIFEST_DIR"));let root=source.join("target/test-data").join(format!("wal-{}-{}",std::process::id(),std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));fs::create_dir_all(root.join("data")).unwrap();
  for name in ["server","maps","items","npcs","growth","skills","monsters","progression","services","particles"]{fs::copy(source.join(format!("data/{name}.json")),root.join(format!("data/{name}.json"))).unwrap();}
  let mut w=World::load(&root).unwrap();let a=w.login(Command::Register{protocol:PROTOCOL,name:"WAL A".into()}).unwrap().0;let b=w.login(Command::Register{protocol:PROTOCOL,name:"WAL B".into()}).unwrap().0;fs::create_dir_all(root.join("transactions")).unwrap();(w,a,b)
 }
 #[test]fn deferred_group_is_durable_before_json_and_finish_checkpoints(){
  let(mut w,a,b)=fixture();let original=fs::read(w.root.join(format!("players/{a}.json"))).unwrap();let store=Store::start(&w.root).unwrap();
  begin(&w.root);w.progress_command(&a,"learn","fire_wave").unwrap();w.players.get_mut(&a).unwrap().progress.coins=12;w.players.get_mut(&b).unwrap().progress.coins=34;
  journal::commit(&w.root,&[w.players[&a].clone(),w.players[&b].clone()]).unwrap();let captured=take();assert_eq!(captured.len(),2);
  assert_eq!(fs::read(w.root.join(format!("players/{a}.json"))).unwrap(),original);
  store.commit(captured).unwrap();assert!(fs::metadata(w.root.join("transactions/active.wal")).unwrap().len()>0);
  store.finish().unwrap();let loaded=World::load(&w.root).unwrap();assert_eq!(loaded.players[&a].progress.coins,12);assert_eq!(loaded.players[&b].progress.coins,34);assert_eq!(loaded.players[&a].progress.skills["fire_wave"],1);
 }
 #[test]fn torn_tail_never_partially_applies_and_recovery_is_idempotent(){
  let(w,a,b)=fixture();let root=&w.root;let mut pa=w.players[&a].clone();let mut pb=w.players[&b].clone();pa.progress.coins=10;pb.progress.coins=20;
  let frame=encode(1,&[pa.clone(),pb.clone()]).unwrap();let path=root.join("transactions/active.wal");let original=fs::read(root.join(format!("players/{a}.json"))).unwrap();
  for n in [0,1,15,16,frame.len()/2,frame.len()-1]{fs::write(&path,&frame[..n]).unwrap();recover(root).unwrap();assert_eq!(fs::read(root.join(format!("players/{a}.json"))).unwrap(),original);}
  fs::write(&path,&frame).unwrap();recover(root).unwrap();let before=fs::read(root.join(format!("players/{a}.json"))).unwrap();recover(root).unwrap();assert_eq!(fs::read(root.join(format!("players/{a}.json"))).unwrap(),before);
  let loaded=World::load(root).unwrap();assert_eq!((loaded.players[&a].progress.coins,loaded.players[&b].progress.coins),(10,20));
 }
 #[test]fn complete_corruption_and_missing_sequence_fail_without_touching_players(){
  let(w,a,_)=fixture();let path=w.root.join("transactions/active.wal");let player=w.root.join(format!("players/{a}.json"));let before=fs::read(&player).unwrap();
  let mut bytes=encode(1,&[w.players[&a].clone()]).unwrap();bytes[20]^=1;fs::write(&path,bytes).unwrap();assert!(recover(&w.root).is_err());assert_eq!(fs::read(&player).unwrap(),before);
  fs::write(&path,encode(2,&[w.players[&a].clone()]).unwrap()).unwrap();assert!(recover(&w.root).is_err());assert_eq!(fs::read(&player).unwrap(),before);
 }
 #[test]fn failed_checkpoint_keeps_committed_group_for_recovery(){
  let(w,a,b)=fixture();let root=&w.root;let mut pa=w.players[&a].clone();let mut pb=w.players[&b].clone();pa.progress.coins=111;pb.progress.coins=222;
  let store=Store::start(root).unwrap();store.commit(vec![vec![pa,pb]]).unwrap();let players=root.join("players");fs::rename(&players,root.join("held-players")).unwrap();fs::write(&players,b"blocked").unwrap();assert!(store.finish().is_err());
  assert!(fs::metadata(root.join("transactions/active.wal")).unwrap().len()>0);fs::remove_file(&players).unwrap();fs::rename(root.join("held-players"),&players).unwrap();
  recover(root).unwrap();let loaded=World::load(root).unwrap();assert_eq!((loaded.players[&a].progress.coins,loaded.players[&b].progress.coins),(111,222));
 }
 #[test]fn failures_at_append_sync_ack_checkpoint_and_compaction_preserve_transactions(){
  for point in 1..=5 {
   let(w,a,b)=fixture();let mut pa=w.players[&a].clone();let mut pb=w.players[&b].clone();pa.progress.coins=17;pb.progress.coins=23;
   let store=Store::open(&w.root,point).unwrap();let result=store.commit(vec![vec![pa,pb]]);assert_eq!(result.is_ok(),point>=4);let finished=store.finish();assert_eq!(finished.is_err(),point==4);
   if point==5{assert!(fs::metadata(w.root.join("transactions/active.wal")).unwrap().len()>0);}
   recover(&w.root).unwrap();let loaded=World::load(&w.root).unwrap();let expected=if point==1{(0,0)}else{(17,23)};
   assert_eq!((loaded.players[&a].progress.coins,loaded.players[&b].progress.coins),expected);
  }
 }
 #[test]fn wal_cap_blocks_further_commits_without_changing_json(){
  let(w,a,_)=fixture();let player=w.root.join(format!("players/{a}.json"));let before=fs::read(&player).unwrap();let store=Store::open(&w.root,6).unwrap();
  assert!(store.commit(vec![vec![w.players[&a].clone()]]).unwrap_err().to_string().contains("64 MiB"));assert!(store.commit(vec![vec![w.players[&a].clone()]]).is_err());store.finish().unwrap();assert_eq!(fs::read(player).unwrap(),before);
 }
 #[test]fn legacy_pending_is_recovered_before_the_new_wal(){
  let(w,a,_)=fixture();let mut old=w.players[&a].clone();old.progress.coins=5;fs::write(w.root.join("transactions/pending.json"),serde_json::to_vec(&vec![old.clone()]).unwrap()).unwrap();old.progress.coins=10;
  fs::write(w.root.join("transactions/active.wal"),encode(1,&[old]).unwrap()).unwrap();let loaded=World::load(&w.root).unwrap();assert_eq!(loaded.players[&a].progress.coins,10);assert!(!w.root.join("transactions/pending.json").exists());
 }
}
