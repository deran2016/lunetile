use super::*;
use std::sync::Arc;
#[derive(Clone)]
pub struct Peer {data:Arc<Value>,until:Option<Instant>,after:Option<(u64,u64)>}
struct PathTail<'a>{data:&'a Value,after:u64}
impl Serialize for PathTail<'_>{fn serialize<S:serde::Serializer>(&self,s:S)->std::result::Result<S::Ok,S::Error>{use serde::ser::SerializeSeq;let mut seq=s.serialize_seq(None)?;if let Some(path)=self.data.as_array(){for p in path{if p["seq"].as_u64().unwrap_or(0)>self.after{seq.serialize_element(p)?;}}}seq.end()}}
struct Motion<'a>{data:&'a Value,after:u64,expired:bool}
impl Serialize for Motion<'_>{fn serialize<S:serde::Serializer>(&self,s:S)->std::result::Result<S::Ok,S::Error>{use serde::ser::SerializeMap;let Some(object)=self.data.as_object()else{return self.data.serialize(s);};let mut map=s.serialize_map(Some(object.len()))?;
 for(k,v)in object{match k.as_str(){"path"=>map.serialize_entry(k,&PathTail{data:v,after:self.after})?,"moving" if self.expired=>map.serialize_entry(k,&false)?,"lead_x" if self.expired=>map.serialize_entry(k,&object["x"])?,"lead_y" if self.expired=>map.serialize_entry(k,&object["y"])?,_=>map.serialize_entry(k,v)?,}}map.end()}}
impl Serialize for Peer {
 fn serialize<S:serde::Serializer>(&self,s:S)->std::result::Result<S::Ok,S::Error>{
  use serde::ser::SerializeMap;let object=self.data.as_object().ok_or_else(||serde::ser::Error::custom("Invalid peer snapshot"))?;let mut map=s.serialize_map(Some(object.len()))?;let expired=self.until.is_some_and(|t|Instant::now()>=t);
  for(k,v)in object{match k.as_str(){"motion"=>map.serialize_entry(k,&Motion{data:v,after:self.after.map_or(0,|a|a.0),expired:false})?,"relay"=>map.serialize_entry(k,&Motion{data:v,after:self.after.map_or(0,|a|a.1),expired})?,_=>map.serialize_entry(k,v)?,}}map.end()
 }
}
struct Personal {base:Arc<Value>,stats:Arc<Value>,cooldowns:BTreeMap<String,Instant>}
struct MapView {map:Arc<Value>,npcs:Arc<Value>,monsters:Arc<Value>,projectiles:Vec<Arc<combat::Projectile>>}
#[derive(Serialize)]
pub struct State {
 #[serde(flatten)]base:Arc<Value>,#[serde(rename="self")]me:Value,
 players:Vec<Peer>,npcs:Arc<Value>,monsters:Arc<Value>,projectiles:Vec<Value>,map:Arc<Value>,
 chat:Arc<Value>,events:Vec<Arc<Value>>,pub event_seq:u64,cooldowns:BTreeMap<String,u64>,notice:String,move_ack:MoveAck,
}
impl State {pub fn trim_paths(&mut self,cursors:&mut BTreeMap<(String,String),u64>){
 cursors.retain(|(id,_),_|self.players.iter().any(|p|p.data["id"].as_str()==Some(id.as_str())));
 for p in &mut self.players{let id=p.data["id"].as_str().unwrap_or("");let mut after=[0,0];for(i,kind)in ["motion","relay"].iter().enumerate(){let key=(id.to_owned(),kind.to_string());after[i]=cursors.get(&key).copied().unwrap_or(0);if let Some(seq)=p.data[*kind]["path"].as_array().and_then(|v|v.last()).and_then(|v|v["seq"].as_u64()){cursors.insert(key,seq);}}p.after=Some((after[0],after[1]));}
}}
pub struct View {base:Arc<Value>,stats:Arc<Value>,me:Peer,players:Vec<Peer>,map:Arc<MapView>,chat:Arc<Value>,events:Vec<Arc<Value>>,event_seq:u64,oldest_event:u64,cooldowns:BTreeMap<String,Instant>,ack:MoveAck}
impl View {
 pub fn response(self,notice:String)->Result<State>{
  let current=self.event_seq;self.response_since(notice,current)
 }
 pub fn response_since(mut self,notice:String,after:u64)->Result<State>{
  if after<self.oldest_event.saturating_sub(1){return Err("Event backlog exceeded; reconnect to synchronize".into());}
  self.events.retain(|e|e["seq"].as_u64().is_some_and(|seq|seq>after));
  let now=Instant::now();let mut me=serde_json::to_value(&self.me)?;
  for(k,v)in self.stats.as_object().ok_or("Invalid snapshot stats")?{me[k]=v.clone();}
  Ok(State{base:self.base,me,players:self.players,npcs:self.map.npcs.clone(),monsters:self.map.monsters.clone(),projectiles:self.map.projectiles.iter().map(|p|p.public(now)).collect(),map:self.map.map.clone(),chat:self.chat,events:self.events,event_seq:self.event_seq,cooldowns:self.cooldowns.into_iter().map(|(id,t)|(id,t.saturating_duration_since(now).as_millis()as u64)).collect(),notice,move_ack:self.ack})
 }
}
pub struct Published {world:World,pub catalog:Arc<Value>,people:BTreeMap<String,Arc<Personal>>,peers:BTreeMap<String,Peer>,maps:BTreeMap<u32,Arc<MapView>>,chat:Arc<Value>,pub acks:BTreeMap<String,MoveAck>}
impl Published {
 pub fn character(&self,id:&str)->Option<Value>{self.world.players.get(id).map(|p|{let mut v=p.public();v["job"]=json!(p.progress.job);v["map_name"]=json!(self.world.maps[&p.position.map_id].name);v})}
 pub fn credentials(&self,id:&str,token:&str)->Result<accounts::Character>{let p=self.world.players.get(id).filter(|p|p.token==token).ok_or("기존 캐릭터 프로필을 확인하세요.")?;Ok(accounts::Character{id:p.id.clone(),token:p.token.clone(),name:p.name.clone(),character:p.character.clone(),pending:false})}
 pub fn character_names(&self)->BTreeSet<String>{self.world.players.values().map(|p|p.name.clone()).collect()}
 pub fn has_capacity(&self)->bool{self.world.players.len()<self.world.config.max_accounts}
 pub fn new(world:&World)->Self {
  let catalog=Arc::new(json!({"items":world.items.values().collect::<Vec<_>>(),"skills":world.combat.skills.values().collect::<Vec<_>>(),"progression":world.progression,"services":world.services,"particle_presets":world.combat.particles}));
  let mut p=Self{world:world.clone(),catalog,people:BTreeMap::new(),peers:BTreeMap::new(),maps:BTreeMap::new(),chat:Arc::new(json!([])),acks:BTreeMap::new()};
  p.refresh(&world.players.keys().cloned().collect());p
 }
 fn peer(&mut self,id:&str){let p=&self.world.players[id];self.peers.insert(id.into(),Peer{data:Arc::new(self.world.moving_public(p)),until:self.world.relay_deadline(id),after:None});}
 fn refresh(&mut self,changed:&BTreeSet<String>){
  let w=&self.world;
  self.people.retain(|id,_|w.online.contains(id));self.peers.retain(|id,_|w.online.contains(id));self.acks.retain(|id,_|w.online.contains(id));
  for id in changed.iter().filter(|id|w.online.contains(*id)) {
   let p=&w.players[id];let m=&w.maps[&p.position.map_id];let left=(p.position.x-3).max(0);let top=(p.position.y-3).max(0);
   let passages:Vec<_>=m.passages[top as usize..(p.position.y+4).min(m.height)as usize].iter().map(|row|&row[left as usize..(p.position.x+4).min(m.width)as usize]).collect();
   let stats=w.player_stats(p);
   self.people.insert(id.clone(),Arc::new(Personal{base:Arc::new(json!({"type":"state","progress":p.progress,"inventory":p.inventory,"social":w.social_state(id),"navigation":{"map_id":m.id,"x":left,"y":top,"passages":passages}})),stats:Arc::new(json!({"exp":p.exp,"exp_next":w.combat.growth.needed(p.level),"mp":p.mp,"max_mp":p.max_mp,"attack":stats.attack,"defense":stats.defense})),cooldowns:w.combat.actors.get(id).map(|a|a.cooldowns.clone()).unwrap_or_default()}));
   self.peers.insert(id.clone(),Peer{data:Arc::new(w.moving_public(p)),until:w.relay_deadline(id),after:None});
  }
  // Social visibility also changes for recipients who did not write a player file.
  for(id,p)in &mut self.people {let social=w.social_state(id);if p.base["social"]!=social{let mut base=(*p.base).clone();base["social"]=social;*p=Arc::new(Personal{base:Arc::new(base),stats:p.stats.clone(),cooldowns:p.cooldowns.clone()});}}
  for m in w.maps.values(){
   self.maps.insert(m.id,Arc::new(MapView{map:Arc::new(json!({"id":m.id,"name":m.name})),npcs:Arc::new(json!(w.npcs.values().filter(|n|n.position.map_id==m.id).collect::<Vec<_>>())),monsters:Arc::new(json!(w.combat.monsters.values().filter(|mob|mob.position.map_id==m.id&&mob.hp>0).map(|mob|json!({"id":mob.id,"name":w.combat.definitions[&mob.kind].name,"character":w.combat.definitions[&mob.kind].character,"position":mob.position,"direction":mob.direction,"hp":mob.hp,"max_hp":w.combat.definitions[&mob.kind].hp})).collect::<Vec<_>>())),projectiles:w.combat.projectiles.iter().filter(|p|p.target.map_id==m.id).cloned().map(Arc::new).collect()}));
  }
  self.chat=Arc::new(json!(w.chat));
 }
 pub fn commit(&mut self,world:&World,changed:&BTreeSet<String>){world.publish_changed(&mut self.world,changed);self.refresh(changed);}
 pub fn preview(&mut self,id:&str,origin:[i32;2],epoch:u64,elapsed:u64,parts:&[PreviewPart],moving:bool,direction:u8)->Result<String>{
  if !self.world.online.contains(id){return Err("Not connected".into());}
  let result=self.world.preview(id,origin,epoch,elapsed,parts,moving,direction);self.peer(id);result
 }
 pub fn cancel(&mut self,id:&str){if self.world.players.contains_key(id){self.world.cancel_preview(id);self.peer(id);}}
 pub fn view(&self,id:&str)->Result<View>{
  let p=self.people.get(id).ok_or("Not connected")?;let map_id=self.world.players[id].position.map_id;
  Ok(View{base:p.base.clone(),stats:p.stats.clone(),me:self.peers[id].clone(),players:self.peers.iter().filter(|(id,_)|self.world.players[*id].position.map_id==map_id).map(|(_,p)|p.clone()).collect(),map:self.maps[&map_id].clone(),chat:self.chat.clone(),events:self.world.events.iter().filter(|(m,recipient,_)|*m==map_id&&recipient.as_ref().is_none_or(|p|p==id)).map(|(_,_,v)|v.clone()).collect(),event_seq:self.world.event_seq,oldest_event:self.world.events.first().and_then(|(_,_,v)|v["seq"].as_u64()).unwrap_or(0),cooldowns:p.cooldowns.clone(),ack:self.acks.get(id).cloned().unwrap_or_default()})
 }
}
