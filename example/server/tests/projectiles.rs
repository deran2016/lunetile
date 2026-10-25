#![cfg(windows)]
use lunetile_mmo_server::*;
use std::{fs,path::PathBuf,time::{Duration,Instant,SystemTime,UNIX_EPOCH}};
fn fixture()->(World,String) {
 let root=PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("target/test-data").join(format!("throw-{}-{}",std::process::id(),SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));fs::create_dir_all(root.join("data")).unwrap();
 for name in ["server","maps","items","npcs","growth","skills","monsters","progression","services"] {fs::copy(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join(format!("data/{name}.json")),root.join(format!("data/{name}.json"))).unwrap();}
 let mut w=World::load(&root).unwrap();let id=w.login(Command::Register{protocol:PROTOCOL,name:"투척 검사".into()}).unwrap().0;
 w.progress_command(&id,"learn","grenade").unwrap();w.npcs.clear();for d in w.combat.definitions.values_mut(){d.move_ms=60000;d.attack_ms=60000;}
 (w,id)
}
fn mobs(w:&mut World,points:&[(i32,i32)],hp:u32) {
 let template=w.combat.monsters["sprout_0"].clone();w.combat.monsters.clear();
 for (i,(x,y)) in points.iter().enumerate() {let mut m=template.clone();m.id=format!("probe_{i}");m.hp=hp;m.position=Position{map_id:1,x:*x,y:*y};m.origin=m.position.clone();w.combat.monsters.insert(m.id.clone(),m);}
}
#[test]
fn throw_has_three_tile_range_nine_warning_cells_and_one_delayed_hit_in_all_directions() {
 for (direction,dx,dy) in [(2,0,1),(4,-1,0),(6,1,0),(8,0,-1)] {
  let (mut w,id)=fixture();let p=w.players[&id].position.clone();let target=(p.x+3*dx,p.y+3*dy);
  let points:Vec<_>=(-1..=1).flat_map(|y|(-1..=1).map(move |x|(target.0+x,target.1+y))).chain([(target.0+2,target.1)]).collect();mobs(&mut w,&points,100);
  let now=Instant::now();w.attack(&id,direction,"grenade",now).unwrap();assert_eq!(w.players[&id].mp,40);assert!(w.combat.monsters.values().all(|m|m.hp==100));
  let p=&w.combat.projectiles[0];assert_eq!((p.target.x,p.target.y),target);assert_eq!(p.cells.len(),9);assert_eq!(p.public(now)["flight_ms"],400);
  w.tick(now+Duration::from_millis(999)).unwrap();assert!(w.combat.monsters.values().all(|m|m.hp==100));
  w.tick(now+Duration::from_millis(1000)).unwrap();assert!(w.combat.projectiles.is_empty());
  for i in 0..10 {assert_eq!(w.combat.monsters[&format!("probe_{i}")].hp,if i<9 {70}else{100});}
  w.tick(now+Duration::from_millis(1001)).unwrap();assert_eq!(w.players[&id].mp,40);assert_eq!(w.combat.monsters["probe_0"].hp,70);
 }
}
#[test]
fn explosion_uses_current_monster_positions_but_cast_power_and_target_are_fixed() {
 let (mut w,id)=fixture();let p=w.players[&id].position.clone();let center=(p.x+3,p.y);mobs(&mut w,&[center,(center.0+2,center.1)],100);
 let now=Instant::now();w.attack(&id,6,"grenade",now).unwrap();
 w.combat.monsters.get_mut("probe_0").unwrap().position.x+=2;w.combat.monsters.get_mut("probe_1").unwrap().position.x-=2;
 w.combat.growth.base_attack=1000;w.players.get_mut(&id).unwrap().position.x-=2;let player=w.players[&id].clone();save_player(&w.root,&player).unwrap();
 w.tick(now+Duration::from_secs(1)).unwrap();assert_eq!(w.combat.monsters["probe_0"].hp,100);assert_eq!(w.combat.monsters["probe_1"].hp,70);assert_eq!(w.players[&id].position.x,p.x-2);
}
#[test]
fn walls_npcs_and_map_edges_bound_flight_and_warning_damage_cells() {
 let (mut w,id)=fixture();let p=w.players[&id].position.clone();w.maps.get_mut(&1).unwrap().passages[p.y as usize][(p.x+2) as usize]=15;
 let now=Instant::now();w.attack(&id,6,"grenade",now).unwrap();let throw=&w.combat.projectiles[0];assert_eq!(throw.target.x,p.x+1);assert!(throw.cells.iter().all(|c|c.x<p.x+2));
 let (mut w,id)=fixture();let p=w.players[&id].position.clone();let mut npc:Vec<Npc>=load_json(&w.root.join("data/npcs.json")).unwrap();npc[0].position.x=p.x+2;npc[0].position.y=p.y;w.npcs.insert(npc[0].id.clone(),npc.remove(0));
 w.attack(&id,6,"grenade",Instant::now()).unwrap();assert_eq!(w.combat.projectiles[0].target.x,p.x+1);assert!(!w.combat.projectiles[0].cells.iter().any(|c|c.x==p.x+2&&c.y==p.y));
 let (mut w,id)=fixture();w.players.get_mut(&id).unwrap().position.x=0;w.attack(&id,4,"grenade",Instant::now()).unwrap();assert_eq!(w.combat.projectiles[0].target.x,0);assert!(w.combat.projectiles[0].cells.iter().all(|c|c.x>=0));
}
#[test]
fn cast_validation_and_failed_save_never_consume_mana_or_create_a_projectile() {
 let (mut w,id)=fixture();let now=Instant::now();assert!(w.attack(&id,5,"grenade",now).is_err());assert_eq!(w.players[&id].mp,50);
 w.players.get_mut(&id).unwrap().mp=9;assert!(w.attack(&id,6,"grenade",now).is_err());assert!(w.combat.projectiles.is_empty());w.players.get_mut(&id).unwrap().mp=50;
 let path=w.root.join("players");fs::rename(&path,w.root.join("players-held")).unwrap();fs::write(&path,b"fail").unwrap();assert!(w.attack(&id,6,"grenade",now).is_err());assert_eq!(w.players[&id].mp,50);assert!(w.combat.projectiles.is_empty());
 fs::remove_file(&path).unwrap();fs::rename(w.root.join("players-held"),path).unwrap();w.attack(&id,6,"grenade",now).unwrap();assert!(w.attack(&id,6,"grenade",now+Duration::from_millis(1999)).is_err());assert_eq!(w.players[&id].mp,40);
}
#[test]
fn published_state_recovers_warning_for_a_late_observer_and_removes_it_after_explosion() {
 let (mut w,id)=fixture();let mut published=World::load(&w.root).unwrap();let now=Instant::now();w.attack(&id,6,"grenade",now).unwrap();w.publish(&mut published);
 let state=published.state(&id,"");assert_eq!(state["projectiles"].as_array().unwrap().len(),1);assert_eq!(state["projectiles"][0]["delay_ms"],1000);assert!(state["projectiles"][0].get("token").is_none());
 w.tick(now+Duration::from_secs(1)).unwrap();w.publish(&mut published);assert!(published.state(&id,"")["projectiles"].as_array().unwrap().is_empty());
}
#[test]
fn delayed_multi_kill_journal_recovers_all_exp_and_quest_credit_without_second_mana_cost() {
 let (mut w,a)=fixture();let b=w.login(Command::Register{protocol:PROTOCOL,name:"보상 검사".into()}).unwrap().0;w.service_command(&a,"quest_accept","quest_01",1).unwrap();w.service_command(&b,"quest_accept","quest_01",1).unwrap();
 let p=w.players[&a].position.clone();mobs(&mut w,&[(p.x+3,p.y-1),(p.x+3,p.y),(p.x+3,p.y+1)],20);for m in w.combat.monsters.values_mut(){m.damage.insert(b.clone(),10);}
 let now=Instant::now();w.attack(&a,6,"grenade",now).unwrap();let blocked=w.root.join(format!("players/{b}.json"));fs::remove_file(&blocked).unwrap();fs::create_dir(&blocked).unwrap();
 assert!(w.tick(now+Duration::from_secs(1)).is_err());assert!(w.root.join("transactions/pending.json").exists());assert_eq!(w.players[&a].exp,0);assert!(w.combat.monsters.values().all(|m|m.hp==20));
 fs::remove_dir(&blocked).unwrap();let loaded=World::load(&w.root).unwrap();assert_eq!((loaded.players[&a].exp,loaded.players[&b].exp),(21,9));assert_eq!(loaded.players[&a].mp,40);assert_eq!(loaded.players[&a].progress.quests["quest_01"],3);assert_eq!(loaded.players[&b].progress.quests["quest_01"],3);
 let again=World::load(&w.root).unwrap();assert_eq!(again.players[&a].exp+again.players[&b].exp,30);assert!(again.combat.projectiles.is_empty());
}
#[test]
fn malformed_projectile_settings_are_rejected_without_rewriting_accounts() {
 let (w,id)=fixture();let path=w.root.join("data/skills.json");let original:serde_json::Value=load_json(&path).unwrap();let account=w.root.join(format!("players/{id}.json"));let before=fs::read(&account).unwrap();
 for (field,value) in [("flight_ms",0),("flight_ms",2001),("delay_ms",399),("delay_ms",10001),("radius",0),("radius",4)] {
  let mut data=original.clone();let skill=data.as_array_mut().unwrap().iter_mut().find(|s|s["id"]=="grenade").unwrap();skill["projectile"][field]=value.into();fs::write(&path,serde_json::to_vec(&data).unwrap()).unwrap();assert!(combat::Combat::load(&w.root).is_err());assert_eq!(fs::read(&account).unwrap(),before);
 }
}
