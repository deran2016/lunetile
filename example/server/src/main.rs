use lunetile_mmo_server::{lock_directory,read_frame,write_frame,Command,MoveAck,Result,World,PROTOCOL,storage,metrics,publishing::{Published,View}};
use serde::Serialize;
use lunetile_mmo_server::accounts::{Accounts,Character};
use serde_json::json;
use std::{collections::{BTreeMap,BTreeSet},io::Write,net::{Shutdown,SocketAddr,TcpListener,TcpStream},path::PathBuf,sync::{atomic::{AtomicBool,AtomicUsize,Ordering},mpsc,Arc,Mutex},thread,time::{Duration,Instant}};
static STOP:AtomicBool=AtomicBool::new(false);
static QUEUED:AtomicUsize=AtomicUsize::new(0);
#[cfg(windows)]
unsafe extern "system" fn console_event(kind:u32)->i32 {if kind<=2{STOP.store(true,Ordering::SeqCst);1}else{0}}
#[derive(Clone)]
struct Link {out:mpsc::SyncSender<String>,pending:Arc<AtomicUsize>,socket:Arc<TcpStream>}
impl Link {fn notify(&self,notice:String){if self.out.try_send(notice).is_err(){metrics::record("send_queue_overflow",1);let _=self.socket.shutdown(Shutdown::Both);}}}
struct Session {link:Link,ack:MoveAck,last_move:Instant,last_chat:Instant}
enum Task {
 Provision{character:Character,reply:mpsc::SyncSender<std::result::Result<(),String>>},
 Login{command:Command,link:Link,reply:mpsc::SyncSender<std::result::Result<(String,String),String>>},
 Command{id:String,command:Command,queued:Instant},Disconnect(String),
}
struct ConnectionGuard {id:String,tasks:mpsc::SyncSender<Task>}
impl Drop for ConnectionGuard {fn drop(&mut self){let _=self.tasks.send(Task::Disconnect(self.id.clone()));}}
fn write_serialized(stream:&mut TcpStream,data:&impl Serialize)->Result<()> {
 let began=Instant::now();let bytes=serde_json::to_vec(data)?;metrics::elapsed("state_serialize",began);
 if bytes.len()>lunetile_mmo_server::MAX_RESPONSE{return Err("Response exceeds protocol limit".into());}
 let began=Instant::now();stream.write_all(&(bytes.len()as u32).to_be_bytes())?;stream.write_all(&bytes)?;metrics::elapsed("socket_send",began);Ok(())
}
fn view(published:&Mutex<Published>,id:&str)->Result<View>{let began=Instant::now();let view=published.lock().map_err(|_|"Published lock")?.view(id)?;metrics::elapsed("snapshot_acquire",began);Ok(view)}
fn world_worker(mut world:World,published:Arc<Mutex<Published>>,receive:mpsc::Receiver<Task>)->Result<()> {
 let store=storage::Store::start(&world.root)?;let mut sessions:BTreeMap<String,Session>=BTreeMap::new();let mut next_tick=Instant::now();let mut last_tick=next_tick;
 let result=(||->Result<()>{loop {
  let timeout=next_tick.saturating_duration_since(Instant::now()).min(Duration::from_millis(50));
  let first=match receive.recv_timeout(timeout){Ok(t)=>Some(t),Err(mpsc::RecvTimeoutError::Timeout)=>None,Err(mpsc::RecvTimeoutError::Disconnected)=>break};
  if first.is_none()&&STOP.load(Ordering::SeqCst){break;}
  let began=Instant::now();let mut batch=first.into_iter().collect::<Vec<_>>();
  if !batch.is_empty(){let deadline=began+Duration::from_millis(5);while batch.len()<64&&Instant::now()<deadline&&Instant::now()<next_tick{
   match receive.recv_timeout((deadline.min(next_tick)).saturating_duration_since(Instant::now())){Ok(t)=>batch.push(t),Err(_)=>break,}
  }}
  metrics::gauge("batch_commands",batch.len()as u64);let computing=Instant::now();
  storage::begin(&world.root);let mut changed=BTreeSet::new();let mut replies=Vec::new();let mut logins=Vec::new();let mut provisions=Vec::new();let mut failure=None;
  for task in batch {match task {
   Task::Provision{character,reply}=>{let result=world.provision(&character).map_err(|e|e.to_string());if result.is_ok(){changed.insert(character.id.clone());}provisions.push((reply,result));}
   Task::Login{command,link,reply}=>{
    let login=world.login(command).map_err(|e|e.to_string());
    if let Ok((id,_))=&login{changed.insert(id.clone());let last=Instant::now()-Duration::from_secs(1);sessions.insert(id.clone(),Session{link,ack:MoveAck::default(),last_move:last,last_chat:last});}
    logins.push((reply,login));
   }
   Task::Disconnect(id)=>{world.online.remove(&id);sessions.remove(&id);}
   Task::Command{id,command,queued}=>{
    metrics::gauge("world_queue",QUEUED.fetch_sub(1,Ordering::SeqCst).saturating_sub(1)as u64);
    metrics::elapsed("request_wait",queued);let command_began=Instant::now();
    if let Some(session)=sessions.get_mut(&id){let is_move=matches!(&command,Command::Move{..});
     let notice=session.ack.process(&mut world,&id,command,&mut session.last_move,&mut session.last_chat).unwrap_or_else(|e|e.to_string());
     changed.insert(id.clone());let failed=is_move&&!session.ack.accepted;replies.push((id,notice,failed));
    }
    metrics::elapsed("command_execute",command_began);
   }
  }}
  let now=Instant::now();if now>=next_tick&&!STOP.load(Ordering::SeqCst){
   metrics::record("tick_interval",now.duration_since(last_tick).as_micros()as u64);last_tick=now;
   let tick_began=Instant::now();if let Err(e)=world.tick(now){failure=Some(e);}metrics::elapsed("world_tick",tick_began);
   next_tick=now+Duration::from_millis(100);
  }
  let records=storage::take();for record in &records{for p in record{changed.insert(p.id.clone());}}
  metrics::elapsed("world_compute",computing);
  if let Some(e)=failure{return Err(e);}
  store.commit(records)?;
  let began=Instant::now();{
   let mut p=published.lock().map_err(|_|"Published lock")?;p.commit(&world,&changed);
   for(id,session)in &sessions{p.acks.insert(id.clone(),session.ack.clone());}
   for(id,_,failed)in &replies{if *failed{p.cancel(id);}}
  }metrics::elapsed("snapshot_publish",began);
  for(reply,login)in logins{let _=reply.send(login);}
  for(reply,result)in provisions{let _=reply.send(result);}
  for(id,notice,_)in replies{if let Some(session)=sessions.get(&id){session.link.pending.fetch_sub(1,Ordering::SeqCst);session.link.notify(notice);}}
 }Ok(())})();
 let finished=store.finish();result.and(finished)
}
fn lobby(stream:&mut TcpStream,first:Command,tasks:&mpsc::SyncSender<Task>,published:&Mutex<Published>,accounts:&Arc<Accounts>)->Result<(Command,Option<lunetile_mmo_server::accounts::Guard>)> {
 let mut command=first;let mut guard:Option<lunetile_mmo_server::accounts::Guard>=None;let mut attempts=0;let mut requests=0;let mut window=Instant::now();
 loop {
  if window.elapsed()>=Duration::from_secs(1){requests=0;window=Instant::now();}requests+=1;if requests>16{return Err("Lobby rate exceeded".into());}
  let registering=matches!(&command,Command::AccountRegister{..});
  let result=(||->Result<Option<Command>> {match command {
   Command::AccountRegister{protocol,username,password}|Command::AccountLogin{protocol,username,password}=>{
    if protocol!=PROTOCOL{return Err("서버와 클라이언트를 함께 업데이트하세요.".into());}
    if guard.is_some(){return Err("이미 로그인했습니다.".into());}attempts+=1;if attempts>6{return Err("인증 시도 한도를 넘었습니다. 재접속하세요.".into());}
    guard=Some(accounts.authenticate(&username,&password,registering)?);
   }
   Command::AccountPoll=>{},
   Command::CharacterCreate{slot,appearance,name:nickname}=>{
    let name=&guard.as_ref().ok_or("먼저 로그인하세요.")?.username;
    let names=published.lock().map_err(|_|"Published lock")?.character_names();
    accounts.create(name,slot,appearance,&nickname,&names,||published.lock().is_ok_and(|p|p.has_capacity()),|c|{
     let(send,receive)=mpsc::sync_channel(1);tasks.try_send(Task::Provision{character:c.clone(),reply:send}).map_err(|_|"World queue unavailable")?;receive.recv_timeout(Duration::from_secs(10))?.map_err(Into::into)
    })?;
   }
   Command::CharacterClaim{id,token}=>{
    let name=&guard.as_ref().ok_or("먼저 로그인하세요.")?.username;
    let character=published.lock().map_err(|_|"Published lock")?.credentials(&id,&token)?;accounts.claim(name,character)?;
   }
   Command::CharacterSelect{slot}=>{
    let name=&guard.as_ref().ok_or("먼저 로그인하세요.")?.username;let chars=accounts.characters(name)?;
    let c=chars.get(slot).and_then(Option::as_ref).ok_or("캐릭터를 먼저 생성하세요.")?;
    return Ok(Some(Command::Login{protocol:PROTOCOL,id:c.id.clone(),token:c.token.clone()}));
   }
   legacy@Command::Register{..}=>return Ok(Some(legacy)),
   legacy@Command::Login{..}=>{
    if let Command::Login{id,..}=&legacy{if accounts.owned(id)?{return Err("계정에 연결된 캐릭터입니다. 아이디와 비밀번호로 로그인하세요.".into());}}
    return Ok(Some(legacy));
   }
   _=>return Err("로그인이 필요합니다.".into()),
  }Ok(None)})();
  match result {
   Ok(Some(selected))=>return Ok((selected,guard)),
   Ok(None)=>{
    let name=guard.as_ref().map(|g|g.username.clone());let chars=if let Some(name)=&name{let slots=accounts.characters(name)?;let p=published.lock().map_err(|_|"Published lock")?;slots.iter().map(|c|c.as_ref().and_then(|c|p.character(&c.id))).collect::<Vec<_>>()}else{vec![None,None,None]};
    write_frame(stream,&json!({"type":"account","protocol":PROTOCOL,"username":name,"characters":chars,"appearances":lunetile_mmo_server::accounts::APPEARANCES}))?;
   }
   Err(e)=>write_frame(stream,&json!({"type":"account_error","message":e.to_string()}))?,
  }
  command=read_frame(stream)?;
 }
}
fn session(mut stream:TcpStream,tasks:mpsc::SyncSender<Task>,published:Arc<Mutex<Published>>,accounts:Arc<Accounts>)->Result<()> {
 stream.set_nonblocking(false)?;
 stream.set_read_timeout(Some(Duration::from_secs(10)))?;stream.set_write_timeout(Some(Duration::from_secs(2)))?;stream.set_nodelay(true)?;
 let first=read_frame(&mut stream)?;let(first,_account)=lobby(&mut stream,first,&tasks,&published,&accounts)?;
 let (out,receive)=mpsc::sync_channel::<String>(32);let pending=Arc::new(AtomicUsize::new(0));let socket=Arc::new(stream.try_clone()?);
 let link=Link{out,pending:pending.clone(),socket:socket.clone()};let (reply,login)=mpsc::sync_channel(1);
 tasks.try_send(Task::Login{command:first,link:link.clone(),reply}).map_err(|_|"World queue unavailable")?;
 let(id,token)=match login.recv_timeout(Duration::from_secs(10))?{Ok(login)=>login,Err(message)=>{write_frame(&mut stream,&serde_json::json!({"type":"error","message":message}))?;return Ok(());}};
 let guard=ConnectionGuard{id:id.clone(),tasks:tasks.clone()};
 let writer_socket=socket.clone();let writer_id=id.clone();let writer_published=published.clone();
 let writer=thread::Builder::new().name("client-send".into()).spawn(move||->std::result::Result<(),String>{
  let result=(||->Result<()>{let mut stream=writer_socket.try_clone()?;let catalog=writer_published.lock().map_err(|_|"Published lock")?.catalog.clone();
   let state=view(&writer_published,&writer_id)?.response("Z 공격 · X 스킬 · K 스킬 창 · Enter 채팅".into())?;
   #[derive(Serialize)]struct Welcome<'a>{#[serde(rename="type")]kind:&'static str,protocol:u32,id:&'a str,token:String,catalog:Arc<serde_json::Value>,state:lunetile_mmo_server::publishing::State}
   let mut event_cursor=state.event_seq;
   write_serialized(&mut stream,&Welcome{kind:"welcome",protocol:PROTOCOL,id:&writer_id,token,catalog,state})?;
   let mut path_cursors=BTreeMap::new();
   for notice in receive{let began=Instant::now();let mut response=view(&writer_published,&writer_id)?.response_since(notice,event_cursor)?;response.trim_paths(&mut path_cursors);metrics::elapsed("state_build",began);write_serialized(&mut stream,&response)?;event_cursor=response.event_seq;}Ok(())
  })();if let Err(e)=&result{eprintln!("Client sender stopped: {e}");metrics::record("sender_errors",1);}let _=writer_socket.shutdown(Shutdown::Both);result.map_err(|e|e.to_string())
 })?;
 let result=(||->Result<()>{let mut window=Instant::now();let mut requests=0;loop{
  let command=read_frame(&mut stream)?;if window.elapsed()>=Duration::from_secs(1){window=Instant::now();requests=0;}requests+=1;
  if requests>96{return Err("Request rate exceeded".into());}
  match command {
   Command::Poll=>link.notify(String::new()),
   Command::Preview{origin,epoch,elapsed,parts,moving,direction}=>{let began=Instant::now();let result=published.lock().map_err(|_|"Published lock")?.preview(&id,origin,epoch,elapsed,&parts,moving,direction);metrics::elapsed("preview",began);if let Err(e)=result{link.notify(e.to_string());}}
   command=>{
    if pending.fetch_add(1,Ordering::SeqCst)>=32{pending.fetch_sub(1,Ordering::SeqCst);return Err("Connection queue full".into());}
    metrics::gauge("connection_queue",pending.load(Ordering::SeqCst)as u64);metrics::gauge("world_queue",(QUEUED.fetch_add(1,Ordering::SeqCst)+1)as u64);
    if tasks.try_send(Task::Command{id:id.clone(),command,queued:Instant::now()}).is_err(){QUEUED.fetch_sub(1,Ordering::SeqCst);pending.fetch_sub(1,Ordering::SeqCst);metrics::record("world_queue_overflow",1);return Err("World queue full".into());}
   }
  }
 }} )();
 let _=socket.shutdown(Shutdown::Both);drop(link);drop(guard);
 // Disconnect removes the actor's final sender, letting the writer drain and exit.
 let sent=writer.join().map_err(|_|"Client sender panicked")?;result.and(sent.map_err(Into::into))
}
fn main(){if let Err(e)=run(){eprintln!("Server stopped: {e}");std::process::exit(1);}}
fn run()->Result<()> {
 if !cfg!(windows){return Err("Windows builds only".into());}
 let mut args=std::env::args().skip(1);let mut root=std::env::current_exe()?.parent().ok_or("Executable directory")?.to_path_buf();let mut recover=false;let mut metric_path=None;
 while let Some(arg)=args.next(){match arg.as_str(){"--root"=>root=std::path::absolute(PathBuf::from(args.next().ok_or("Missing root")?))?,"--metrics"=>metric_path=Some(PathBuf::from(args.next().ok_or("Missing metrics file")?)),"--recover-only"=>recover=true,_=>return Err("Usage: server [--root FOLDER] [--recover-only] [--metrics FILE]".into())}}
 let _lock=lock_directory(&root)?;let mut world=World::load(&root)?;let accounts=Accounts::open(&mut world)?;
 if recover{println!("Recovery complete. JSON files are ready for offline editing.");return Ok(());}
 if metric_path.is_some(){metrics::enable();}
 #[cfg(windows)]{#[link(name="kernel32")]unsafe extern "system"{fn SetConsoleCtrlHandler(handler:Option<unsafe extern "system" fn(u32)->i32>,add:i32)->i32;}unsafe{SetConsoleCtrlHandler(Some(console_event),1);}}
 let address:SocketAddr=world.config.bind.parse()?;let listener=TcpListener::bind(address)?;listener.set_nonblocking(true)?;
 println!("Lunetile MMO protocol {PROTOCOL} | {} | max {} connections",listener.local_addr()?,world.config.max_clients);
 println!("Durable WAL, JSON checkpoint every 1s. Stop/recover before editing. Root: {}",root.display());
 let max=world.config.max_clients;let published=Arc::new(Mutex::new(Published::new(&world)));let (send,receive)=mpsc::sync_channel(1024);let visible=published.clone();
 let actor=thread::Builder::new().name("world-owner".into()).spawn(move||world_worker(world,visible,receive))?;
 let active=Arc::new(AtomicUsize::new(0));let sockets=Arc::new(Mutex::new(BTreeMap::<usize,TcpStream>::new()));let mut jobs=Vec::new();let mut serial=0;let mut last_metrics=Instant::now();
 while !STOP.load(Ordering::SeqCst)&&!actor.is_finished(){
  if last_metrics.elapsed()>=Duration::from_secs(5){if let Some(path)=&metric_path{if metrics::write(path).is_err(){eprintln!("Metrics output unavailable; server continues.");}}last_metrics=Instant::now();}
  jobs.retain(|j:&thread::JoinHandle<()>|!j.is_finished());
  let stream=match listener.accept(){Ok((s,_))=>s,Err(e)if e.kind()==std::io::ErrorKind::WouldBlock=>{thread::sleep(Duration::from_millis(2));continue;},Err(e)=>return Err(e.into())};
  if active.load(Ordering::SeqCst)>=max{drop(stream);continue;}
  serial+=1;let key=serial;sockets.lock().map_err(|_|"Socket registry")?.insert(key,stream.try_clone()?);active.fetch_add(1,Ordering::SeqCst);
  let(active,sockets,tasks,published,accounts)=(active.clone(),sockets.clone(),send.clone(),published.clone(),accounts.clone());
  // Parser errors can contain untrusted strings; never log received JSON or credentials.
  jobs.push(thread::Builder::new().name("client-read".into()).spawn(move||{let _=session(stream,tasks,published,accounts);if let Ok(mut s)=sockets.lock(){s.remove(&key);}active.fetch_sub(1,Ordering::SeqCst);})?);
 }
 STOP.store(true,Ordering::SeqCst);for socket in sockets.lock().map_err(|_|"Socket registry")?.values(){let _=socket.shutdown(Shutdown::Both);}
 drop(send);let result=actor.join().map_err(|_|"World owner panicked")?;for job in jobs{let _=job.join();}
 if let Some(path)=&metric_path{let _=metrics::write(path);}result
}
