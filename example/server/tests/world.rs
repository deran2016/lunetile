#![cfg(windows)]
use lunetile_mmo_server::*;
use serde_json::json;
use std::fs;
use std::io::Cursor;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, Instant};

fn fixture() -> World {
    static NEXT: AtomicU64 = AtomicU64::new(0);
    let source = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let root = source.join("target/test-data").join(format!("{}-{}-{}", std::process::id(),
        std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos(), NEXT.fetch_add(1,Ordering::SeqCst)));
    fs::create_dir_all(root.join("data")).unwrap();
    for name in ["server", "maps", "items", "npcs", "growth", "skills", "monsters"] {
        fs::copy(source.join(format!("data/{name}.json")),root.join(format!("data/{name}.json"))).unwrap();
    }
    World::load(&root).unwrap()
}

fn register(world: &mut World) -> (String, String) {
    world.login(Command::Register { protocol: PROTOCOL, name: "테스트 모험가".into() }).unwrap()
}

fn command(world: &mut World, id: &str, command: Command) -> Result<String> {
    let mut time = Instant::now()-Duration::from_secs(1);
    let mut chat = time;
    world.command(id,command,&mut time,&mut chat)
}

#[test]
fn reward_is_once_and_inventory_survives_restart() {
    let mut world=fixture(); let (id,token)=register(&mut world);
    command(&mut world,&id,Command::Talk { npc_id:"guide".into() }).unwrap();
    command(&mut world,&id,Command::Talk { npc_id:"guide".into() }).unwrap();
    assert_eq!(world.players[&id].inventory["potion"],5);
    command(&mut world,&id,Command::Use { item_id:"potion".into() }).unwrap();
    assert_eq!(world.players[&id].hp,100);
    let mut reloaded=World::load(&world.root).unwrap();
    reloaded.login(Command::Login { protocol:PROTOCOL,id:id.clone(),token }).unwrap();
    assert_eq!(reloaded.players[&id].inventory["potion"],4);
    assert!(reloaded.players[&id].claimed_npcs.contains("guide"));
    assert!(world.root.join(format!("players/{id}.json.bak")).is_file());
}

#[test]
fn login_rejects_wrong_secret_duplicate_session_and_name() {
    let mut world=fixture(); let (id,token)=register(&mut world);
    assert!(world.login(Command::Login { protocol:PROTOCOL,id:id.clone(),token:"wrong".into() }).is_err());
    assert!(world.login(Command::Login { protocol:PROTOCOL,id:id.clone(),token }).is_err());
    assert!(world.login(Command::Register { protocol:PROTOCOL,name:"테스트 모험가".into() }).is_err());
    let state=world.state(&id,"").to_string();
    assert!(!state.contains("token"));
    assert!(!state.contains(&world.players[&id].token));
}

#[test]
fn failed_disk_commit_does_not_grant_items() {
    let mut world=fixture(); let (id,_)=register(&mut world);
    let path=world.root.join(format!("players/{id}.json"));
    let before=fs::read(&path).unwrap();
    fs::create_dir(path.with_extension("json.tmp")).unwrap();
    assert!(command(&mut world,&id,Command::Talk { npc_id:"guide".into() }).is_err());
    assert_eq!(world.players[&id].inventory["potion"],2);
    assert_eq!(fs::read(path).unwrap(),before);
}

#[test]
fn backup_retains_previous_bytes_across_replacements_and_failed_commits() {
    let mut w=fixture();let (id,_)=register(&mut w);let path=w.root.join(format!("players/{id}.json"));
    let old=fs::read(&path).unwrap();command(&mut w,&id,Command::Use{item_id:"potion".into()}).unwrap();
    assert_eq!(fs::read(path.with_extension("json.bak")).unwrap(),old);
    let current=fs::read(&path).unwrap();command(&mut w,&id,Command::Talk{npc_id:"guide".into()}).unwrap();
    assert_eq!(fs::read(path.with_extension("json.bak")).unwrap(),current);
    assert_ne!(fs::read(&path).unwrap(),current);
    assert!(!path.with_extension("json.bak.tmp").exists());
}

#[test]
fn full_stack_never_partly_grants_a_reward() {
    let mut world=fixture(); let (id,_)=register(&mut world);
    world.players.get_mut(&id).unwrap().inventory.insert("potion".into(),98);
    assert!(command(&mut world,&id,Command::Talk { npc_id:"guide".into() }).is_err());
    assert_eq!(world.players[&id].inventory.len(),2);
    assert!(!world.players[&id].claimed_npcs.contains("guide"));
}

fn movement(w:&World,id:&str,seq:u64,parts:Vec<MovePart>)->Command {
    let (x,y)=w.players[id].motion();Command::Move{seq,origin:[x,y],epoch:0,parts}
}
fn part(direction:u8,ms:u16)->MovePart {MovePart{direction,ms}}

#[test]
fn movement_turns_between_centers_and_keeps_five_tiles_per_second() {
    let mut w=fixture();let (id,_)=register(&mut w);w.npcs.clear();
    let (x,y)=w.players[&id].motion();
    let cmd=movement(&w,&id,1,vec![part(6,35),part(2,35),part(4,35),part(8,35)]);
    command(&mut w,&id,cmd).unwrap();assert_eq!(w.players[&id].motion(),(x,y));
    let path=w.state(&id,"")["self"]["motion"]["path"].clone();
    assert_eq!(path[1]["x"],x+175);assert_eq!(path[2]["y"],y+175);
    assert_eq!(path[3]["x"],x);assert_eq!(path[4]["y"],y);
    let cmd=movement(&w,&id,2,vec![part(6,200)]);command(&mut w,&id,cmd).unwrap();
    assert_eq!(w.players[&id].motion(),(x+1000,y));
    let restored=World::load(&w.root).unwrap();assert_eq!(restored.players[&id].motion(),(x+1000,y));
}

#[test]
fn optional_offsets_preserve_old_files_and_persist_fractional_positions() {
    let mut w=fixture();let (id,token)=register(&mut w);let file=w.root.join(format!("players/{id}.json"));
    let mut old:serde_json::Value=serde_json::from_slice(&fs::read(&file).unwrap()).unwrap();
    old.as_object_mut().unwrap().remove("offset_x");old.as_object_mut().unwrap().remove("offset_y");
    fs::write(&file,serde_json::to_vec(&old).unwrap()).unwrap();let bytes=fs::read(&file).unwrap();
    w=World::load(&w.root).unwrap();assert_eq!(fs::read(&file).unwrap(),bytes);
    w.login(Command::Login{protocol:PROTOCOL,id:id.clone(),token:token.clone()}).unwrap();
    let cmd=movement(&w,&id,1,vec![part(6,35)]);command(&mut w,&id,cmd).unwrap();
    let p=&World::load(&w.root).unwrap().players[&id];assert_eq!(p.offset_x,175);assert_eq!(p.token,token);assert_eq!(p.inventory,w.players[&id].inventory);
    let mut invalid:serde_json::Value=serde_json::from_slice(&fs::read(&file).unwrap()).unwrap();invalid["offset_x"]=json!(500);
    fs::write(&file,serde_json::to_vec(&invalid).unwrap()).unwrap();let bytes=fs::read(&file).unwrap();
    assert!(World::load(&w.root).is_err());assert_eq!(fs::read(file).unwrap(),bytes);
}

#[test]
fn movement_checks_both_edges_npcs_corners_and_map_boundary() {
    for blocked in [0,1,2] {
        let mut w=fixture();let (id,_)=register(&mut w);let p=w.players[&id].position.clone();
        if blocked!=2 {w.npcs.clear();w.maps.get_mut(&p.map_id).unwrap().passages[p.y as usize][p.x as usize+usize::from(blocked==1)]|=if blocked==0{4}else{2};}
        let direction=if blocked==2 {2}else{6};let cmd=movement(&w,&id,1,vec![part(direction,200)]);
        command(&mut w,&id,cmd).unwrap();let player=&w.players[&id];assert_eq!(player.position.x,p.x);assert_eq!(player.position.y,p.y);
        assert!(player.offset_x.abs()<=495 && player.offset_y.abs()<=495);
    }
    let mut w=fixture();let (id,_)=register(&mut w);w.npcs.clear();
    let p=w.players[&id].position.clone();w.maps.get_mut(&p.map_id).unwrap().passages[p.y as usize+1][p.x as usize+1]=15;
    let cmd=movement(&w,&id,1,vec![part(6,90),part(2,90)]);command(&mut w,&id,cmd).unwrap();
    let cmd=movement(&w,&id,2,vec![part(6,100)]);command(&mut w,&id,cmd).unwrap();
    assert_eq!(w.players[&id].position.x,p.x+1);assert_eq!(w.players[&id].position.y,p.y);
    let cmd=movement(&w,&id,3,vec![part(2,100)]);command(&mut w,&id,cmd).unwrap();assert_eq!(w.players[&id].position.y,p.y);
    {let player=w.players.get_mut(&id).unwrap();player.position.x=0;player.position.y=0;player.offset_x=0;player.offset_y=0;}
    let cmd=movement(&w,&id,4,vec![part(4,200)]);command(&mut w,&id,cmd).unwrap();assert_eq!(w.players[&id].motion().0,-500);
}

#[test]
fn movement_ack_consumes_errors_without_committing_failed_saves() {
    let mut w=fixture();let (id,_)=register(&mut w);let mut ack=MoveAck::default();
    let mut time=Instant::now()-Duration::from_secs(1);let mut chat=time;
    let cmd=movement(&w,&id,1,vec![part(3,100)]);assert!(ack.process(&mut w,&id,cmd,&mut time,&mut chat).is_err());
    assert_eq!(ack.seq,1);assert!(!ack.accepted);
    let cmd=movement(&w,&id,2,vec![part(6,100)]);ack.process(&mut w,&id,cmd,&mut time,&mut chat).unwrap();
    let position=w.players[&id].motion();assert_eq!(ack.state(&w,&id,"")["move_ack"],json!({"seq":2,"accepted":true}));
    for seq in [2,4] {let cmd=movement(&w,&id,seq,vec![part(6,10)]);assert!(ack.process(&mut w,&id,cmd,&mut time,&mut chat).is_err());}
    let path=w.root.join(format!("players/{id}.json"));let bytes=fs::read(&path).unwrap();fs::create_dir(path.with_extension("json.tmp")).unwrap();
    time=Instant::now()-Duration::from_secs(1);
    let cmd=movement(&w,&id,3,vec![part(6,100)]);assert!(ack.process(&mut w,&id,cmd,&mut time,&mut chat).is_err());
    assert_eq!(ack.seq,3);assert!(!ack.accepted);assert_eq!(w.players[&id].motion(),position);assert_eq!(fs::read(&path).unwrap(),bytes);
    let cmd=Command::Move{seq:4,origin:[0,0],epoch:0,parts:vec![part(6,1)]};assert!(ack.process(&mut w,&id,cmd,&mut time,&mut chat).is_err());
}

#[test]
fn movement_rejects_speed_spam_overlong_paths_and_old_respawn_epoch() {
    let mut w=fixture();let (id,_)=register(&mut w);let mut time=Instant::now()+Duration::from_millis(200);let mut chat=Instant::now();
    let cmd=movement(&w,&id,1,vec![part(6,100)]);assert!(w.command(&id,cmd,&mut time,&mut chat).is_err());
    for parts in [vec![],vec![part(6,201)],vec![part(6,0)],(0..33).map(|_|part(6,1)).collect()] {
        let cmd=movement(&w,&id,1,parts);assert!(command(&mut w,&id,cmd).is_err());
    }
    let cmd=movement(&w,&id,1,vec![part(6,10)]);
    w.players.get_mut(&id).unwrap().hp=0;let now=Instant::now();w.tick(now).unwrap();w.tick(now+Duration::from_secs(3)).unwrap();
    assert!(command(&mut w,&id,cmd).is_err());
}

#[test]
fn navigation_is_bounded_and_matches_edited_server_passages() {
    let mut world=fixture();let (id,_)=register(&mut world);let p=world.players[&id].position.clone();
    world.maps.get_mut(&p.map_id).unwrap().passages[p.y as usize][p.x as usize+1]=2;
    let state=world.state(&id,"");let nav=&state["navigation"];
    assert_eq!(nav["map_id"],p.map_id);assert_eq!(nav["x"],p.x-3);assert_eq!(nav["y"],p.y-3);
    assert_eq!(nav["passages"].as_array().unwrap().len(),7);assert_eq!(nav["passages"][3][4],2);
    world.players.get_mut(&id).unwrap().position.x=0;world.players.get_mut(&id).unwrap().position.y=0;
    let nav=world.state(&id,"")["navigation"].clone();assert_eq!(nav["x"],0);assert_eq!(nav["y"],0);
    assert_eq!(nav["passages"].as_array().unwrap().len(),4);
    assert!(nav["passages"].as_array().unwrap().iter().all(|r|r.as_array().unwrap().len()==4));
    let (other,_)=world.login(Command::Register{protocol:PROTOCOL,name:"다른 이동자".into()}).unwrap();
    assert_eq!(MoveAck::default().state(&world,&other,"")["move_ack"]["seq"],0);
}

#[test]
fn remote_npc_and_unowned_item_are_rejected() {
    let mut world=fixture(); let (id,_)=register(&mut world);
    world.players.get_mut(&id).unwrap().position.x=0;
    assert!(command(&mut world,&id,Command::Talk { npc_id:"guide".into() }).is_err());
    assert!(command(&mut world,&id,Command::Use { item_id:"village_badge".into() }).is_err());
}

#[test]
fn malformed_and_invented_commands_are_rejected() {
    for value in [json!({"type":"move","seq":1,"direction":6,"inventory":{"potion":999}}),json!({"type":"give","item_id":"potion"}),json!({"type":"move","seq":1,"direction":-1}),json!({"type":"move","direction":6})] {
        assert!(serde_json::from_value::<Command>(value).is_err());
    }
    for bytes in [vec![0,0,0,0],vec![0,1,0,0],vec![0,0,0,10,b'{']] {
        assert!(read_frame(&mut Cursor::new(bytes)).is_err());
    }
    let body=br#"{"type":"poll"}"#;
    let mut bytes=(body.len() as u32).to_be_bytes().to_vec(); bytes.extend(body);
    assert!(matches!(read_frame(&mut Cursor::new(bytes)).unwrap(),Command::Poll));
    assert!(!valid_id("../escape")); assert!(!valid_id("CON"));
}

#[test]
fn invalid_database_stops_startup_without_resetting_players() {
    let mut world=fixture(); let (id,_)=register(&mut world);
    let path=world.root.join(format!("players/{id}.json"));
    fs::write(&path,b"{broken").unwrap();
    assert!(World::load(&world.root).is_err());
    assert_eq!(fs::read(path).unwrap(),b"{broken");
}

#[test]
fn one_server_owns_the_data_folder() {
    let world=fixture();
    let lock=lock_directory(&world.root).unwrap();
    assert!(lock_directory(&world.root).is_err());
    drop(lock);
    assert!(lock_directory(&world.root).is_ok());
}

fn align_monster(world:&mut World)->String {
    let id="sprout_0".to_owned();let p=world.config.spawn.clone();
    let m=world.combat.monsters.get_mut(&id).unwrap();m.position=Position{map_id:p.map_id,x:p.x+1,y:p.y};m.origin=m.position.clone();id
}
#[test]
fn combat_validates_walls_range_mana_and_cooldown() {
    let mut w=fixture();let (id,_)=register(&mut w);let mob=align_monster(&mut w);let now=Instant::now();
    let p=w.config.spawn.clone();w.maps.get_mut(&p.map_id).unwrap().passages[p.y as usize][p.x as usize]|=4;
    w.attack(&id,6,"burst",now).unwrap();assert_eq!(w.players[&id].mp,40);assert_eq!(w.combat.monsters[&mob].hp,30);
    w.maps.get_mut(&p.map_id).unwrap().passages[p.y as usize][p.x as usize]&=!4;
    w.attack(&id,6,"burst",now+Duration::from_secs(2)).unwrap();assert_eq!(w.players[&id].mp,30);assert_eq!(w.combat.monsters[&mob].hp,5);
    assert!(w.attack(&id,6,"burst",now+Duration::from_secs(2)).is_err());
    w.players.get_mut(&id).unwrap().mp=0;
    assert!(w.attack(&id,6,"burst",now+Duration::from_secs(4)).is_err());
    w.players.get_mut(&id).unwrap().position.x=0;
    w.attack(&id,6,"basic",now+Duration::from_secs(4)).unwrap();assert_eq!(w.combat.monsters[&mob].hp,5);
}
#[test]
fn cooperative_reward_is_exact_and_not_repeated() {
    let mut w=fixture();let (a,_)=register(&mut w);
    let (b,_)=w.login(Command::Register{protocol:PROTOCOL,name:"두 번째".into()}).unwrap();let mob=align_monster(&mut w);let now=Instant::now();
    w.attack(&a,6,"basic",now).unwrap();w.attack(&b,6,"basic",now).unwrap();
    w.attack(&b,6,"basic",now+Duration::from_millis(600)).unwrap();
    assert_eq!(w.players[&a].exp,3);assert_eq!(w.players[&b].exp,7);
    w.attack(&a,6,"basic",now+Duration::from_secs(2)).unwrap();assert_eq!(w.players[&a].exp+w.players[&b].exp,10);
    let reloaded=World::load(&w.root).unwrap();assert_eq!(reloaded.players[&a].exp+reloaded.players[&b].exp,10);
    assert!(!w.root.join("transactions/pending.json").exists());
    w.tick(now+Duration::from_secs(6)).unwrap();assert_eq!(w.combat.monsters[&mob].hp,30);
}
#[test]
fn growth_multiple_levels_and_cap_refill_resources() {
    let mut w=fixture();let (id,_)=register(&mut w);let mut p=w.players[&id].clone();p.hp=1;p.mp=0;
    w.combat.growth.grant(&mut p,155);assert_eq!((p.level,p.exp,p.hp,p.max_hp,p.mp),(3,5,140,140,70));
    w.combat.growth.grant(&mut p,100_000);assert_eq!((p.level,p.exp),(w.combat.growth.max_level,0));
}
#[test]
fn legacy_migration_preserves_original_and_identity() {
    let mut w=fixture();let (id,token)=register(&mut w);let path=w.root.join(format!("players/{id}.json"));
    let mut old:serde_json::Value=load_json(&path).unwrap();for key in ["schema","level","exp","mp","max_mp"]{old.as_object_mut().unwrap().remove(key);}
    let bytes=serde_json::to_vec_pretty(&old).unwrap();fs::write(&path,&bytes).unwrap();
    let migrated=World::load(&w.root).unwrap();let p=&migrated.players[&id];assert_eq!(p.token,token);assert_eq!((p.hp,p.mp,p.schema,p.level),(70,50,2,1));
    assert_eq!(fs::read(path.with_extension("json.v1.bak")).unwrap(),bytes);
    World::load(&w.root).unwrap();assert_eq!(fs::read(path.with_extension("json.v1.bak")).unwrap(),bytes);
}
#[test]
fn journal_recovers_partial_group_reward_without_double_grant() {
    let mut w=fixture();let (a,_)=register(&mut w);let (b,_)=w.login(Command::Register{protocol:PROTOCOL,name:"복구 대상".into()}).unwrap();
    let mut pa=w.players[&a].clone();pa.exp=4;let mut pb=w.players[&b].clone();pb.exp=6;
    let transactions=w.root.join("transactions");fs::create_dir_all(&transactions).unwrap();
    fs::write(transactions.join("pending.json"),serde_json::to_vec(&vec![pa.clone(),pb.clone()]).unwrap()).unwrap();
    save_player(&w.root,&pa).unwrap();
    let recovered=World::load(&w.root).unwrap();assert_eq!((recovered.players[&a].exp,recovered.players[&b].exp),(4,6));
    let repeated=World::load(&w.root).unwrap();assert_eq!((repeated.players[&a].exp,repeated.players[&b].exp),(4,6));
}
#[test]
fn failed_attack_save_never_consumes_mana_or_deals_damage() {
    let mut w=fixture();let (id,_)=register(&mut w);let mob=align_monster(&mut w);
    let temporary=w.root.join(format!("players/{id}.json.tmp"));fs::create_dir(temporary).unwrap();
    assert!(w.attack(&id,6,"burst",Instant::now()).is_err());assert_eq!((w.players[&id].mp,w.combat.monsters[&mob].hp),(50,30));
}
#[test]
fn death_respawns_and_idle_mana_regenerates() {
    let mut w=fixture();let (id,_)=register(&mut w);let mob=align_monster(&mut w);let now=Instant::now();
    w.players.get_mut(&id).unwrap().hp=5;
    w.tick(now+Duration::from_secs(2)).unwrap();assert_eq!(w.players[&id].hp,0);
    let cmd=movement(&w,&id,1,vec![part(6,100)]);assert!(command(&mut w,&id,cmd).is_err());
    w.combat.monsters.clear();w.tick(now+Duration::from_secs(3)).unwrap();w.tick(now+Duration::from_secs(6)).unwrap();
    assert_eq!((w.players[&id].hp,w.players[&id].mp),(100,50));
    assert!(w.state(&id,"")["events"].as_array().unwrap().iter().any(|v|v["kind"]=="respawn"));
    w.players.get_mut(&id).unwrap().mp=0;w.tick(now+Duration::from_secs(8)).unwrap();assert_eq!(w.players[&id].mp,5);
    assert_eq!(mob,"sprout_0");
}
#[test]
fn monster_chases_respects_walls_and_returns_inside_leash() {
    let mut w=fixture();let (id,_)=register(&mut w);let mob=align_monster(&mut w);let now=Instant::now();
    w.players.get_mut(&id).unwrap().position.x=12;
    w.tick(now+Duration::from_secs(1)).unwrap();assert_eq!(w.combat.monsters[&mob].position.x,11);
    w.players.get_mut(&id).unwrap().position.x=0;
    w.tick(now+Duration::from_secs(2)).unwrap();assert_eq!(w.combat.monsters[&mob].position.x,10);
    let m=w.combat.monsters.get_mut(&mob).unwrap();m.position.x=16;
    for n in 3..12 {w.tick(now+Duration::from_secs(n)).unwrap();}
    assert_eq!(w.combat.monsters[&mob].position.x,10);
}

#[test]
fn growth_file_updates_derived_caps_without_healing_existing_players() {
    let mut w=fixture();let (id,_)=register(&mut w);let path=w.root.join("data/growth.json");let mut data:serde_json::Value=load_json(&path).unwrap();
    data["base_hp"]=json!(110);data["base_mp"]=json!(70);fs::write(path,serde_json::to_vec(&data).unwrap()).unwrap();
    let reloaded=World::load(&w.root).unwrap();let p=&reloaded.players[&id];assert_eq!((p.hp,p.max_hp,p.mp,p.max_mp),(70,110,50,70));
}
#[test]
fn interrupted_real_kill_transaction_recovers_all_participants() {
    let mut w=fixture();let (a,_)=register(&mut w);let (b,_)=w.login(Command::Register{protocol:PROTOCOL,name:"저널 참가자".into()}).unwrap();
    align_monster(&mut w);let now=Instant::now();w.attack(&a,6,"basic",now).unwrap();w.attack(&b,6,"basic",now).unwrap();
    let blocked_id=std::cmp::max(&a,&b);let blocked=w.root.join(format!("players/{blocked_id}.json.tmp"));fs::create_dir(&blocked).unwrap();
    assert!(w.attack(&a,6,"basic",now+Duration::from_millis(600)).is_err());assert_eq!((w.players[&a].exp,w.players[&b].exp),(0,0));
    assert!(w.root.join("transactions/pending.json").exists());assert!(command(&mut w,&a,Command::Poll).is_err());
    fs::remove_dir(blocked).unwrap();let recovered=World::load(&w.root).unwrap();assert_eq!((recovered.players[&a].exp,recovered.players[&b].exp),(7,3));
}

#[test]
fn monster_cannot_attack_through_a_blocked_tile_edge() {
    let mut w=fixture();let (id,_)=register(&mut w);let mob=align_monster(&mut w);
    let p=w.players[&id].position.clone();let m=w.combat.monsters[&mob].position.clone();
    w.maps.get_mut(&p.map_id).unwrap().passages[p.y as usize][p.x as usize]=15;
    w.maps.get_mut(&m.map_id).unwrap().passages[m.y as usize][m.x as usize]=15;
    w.tick(Instant::now()+Duration::from_secs(2)).unwrap();
    assert_eq!(w.players[&id].hp,70);
}

fn arena(offsets:&[(i32,i32)]) -> (World,String,Vec<String>) {
    let mut w=fixture();let (id,_)=register(&mut w);w.npcs.clear();
    for row in &mut w.maps.get_mut(&1).unwrap().passages {row.fill(0);}
    let template=w.combat.monsters["sprout_0"].clone();w.combat.monsters.clear();let p=w.players[&id].position.clone();
    let mut ids=Vec::new();
    for (i,(x,y)) in offsets.iter().enumerate(){let mut m=template.clone();m.id=format!("test_{i}");m.position=Position{map_id:1,x:p.x+x,y:p.y+y};m.origin=m.position.clone();ids.push(m.id.clone());w.combat.monsters.insert(m.id.clone(),m);}
    (w,id,ids)
}

#[test]
fn fan_attacks_all_front_cells_in_each_direction_once() {
    let local=[(0,0),(1,-1),(1,0),(1,1),(2,0),(3,-3),(3,3),(3,4),(4,0),(-1,0),(0,1)];
    for (direction,fx,fy) in [(2,0,1),(4,-1,0),(6,1,0),(8,0,-1)] {
        let offsets:Vec<_>=local.iter().map(|(f,s)|(f*fx+s*fy,f*fy-s*fx)).collect();
        let (mut w,id,ids)=arena(&offsets);w.attack(&id,direction,"burst",Instant::now()).unwrap();
        for (i,m) in ids.iter().enumerate(){assert_eq!(w.combat.monsters[m].hp,if i<7{5}else{30},"direction {direction}, index {i}");}
        assert_eq!(w.players[&id].mp,40);
        let state=w.state(&id,"");assert_eq!(state["events"].as_array().unwrap().iter().filter(|e|e["kind"]=="attack").count(),1);
    }
    let (mut w,id,ids)=arena(&[(1,-1),(1,0),(1,1),(2,0),(-1,0)]);w.attack(&id,6,"basic",Instant::now()).unwrap();
    for (i,m) in ids.iter().enumerate(){assert_eq!(w.combat.monsters[m].hp,if i<3{20}else{30});}
}

#[test]
fn diagonal_sight_never_cuts_a_wall_or_npc_corner() {
    for npc in [false,true] {
        let (mut w,id,ids)=arena(&[(1,1),(2,2)]);let p=w.players[&id].position.clone();
        if npc {
            w.npcs.insert("blocker".into(),Npc{id:"blocker".into(),name:"벽 역할".into(),character:"001-Fighter01".into(),position:Position{map_id:1,x:p.x+1,y:p.y},dialogue:"test".into(),reward:Default::default()});
        }else{w.maps.get_mut(&1).unwrap().passages[p.y as usize][p.x as usize]|=4;}
        w.attack(&id,6,"burst",Instant::now()).unwrap();
        assert!(ids.iter().all(|m|w.combat.monsters[m].hp==30));assert_eq!(w.players[&id].mp,40);
    }
}

#[test]
fn empty_cast_costs_mana_and_cooldown_but_invalid_cast_does_not() {
    let (mut w,id,_)=arena(&[]);let now=Instant::now();
    assert!(w.attack(&id,3,"burst",now).is_err());assert!(w.attack(&id,6,"invented",now).is_err());assert_eq!(w.players[&id].mp,50);
    w.attack(&id,6,"burst",now).unwrap();assert_eq!(w.players[&id].mp,40);
    assert!(w.attack(&id,6,"burst",now+Duration::from_millis(1199)).is_err());
    w.attack(&id,6,"burst",now+Duration::from_millis(1200)).unwrap();assert_eq!(w.players[&id].mp,30);
    assert_eq!(w.state(&id,"")["events"].as_array().unwrap().iter().filter(|e|e["kind"]=="attack").count(),2);
}

#[test]
fn multi_kill_grants_each_contribution_and_one_mana_cost() {
    let (mut w,a,ids)=arena(&[(1,-1),(1,0),(1,1)]);let (b,_)=w.login(Command::Register{protocol:PROTOCOL,name:"광역 동료".into()}).unwrap();let now=Instant::now();
    w.attack(&a,6,"basic",now).unwrap();w.attack(&b,6,"burst",now).unwrap();
    assert!(ids.iter().all(|m|w.combat.monsters[m].hp==0));assert_eq!((w.players[&a].exp,w.players[&b].exp,w.players[&b].mp),(9,21,40));
    let reloaded=World::load(&w.root).unwrap();assert_eq!(reloaded.players[&a].exp+reloaded.players[&b].exp,30);
    let state=w.state(&b,"");for hit in state["events"].as_array().unwrap().iter().filter(|e|e["kind"]=="damage"&&e["killed"]==true){assert!(hit["position"].is_object());assert_eq!(hit["amount"],20);}
}

#[test]
fn level_up_during_a_fan_never_increases_its_remaining_damage() {
    let (mut w,id,ids)=arena(&[(1,-1),(1,0),(1,1)]);w.players.get_mut(&id).unwrap().exp=45;w.combat.monsters.get_mut(&ids[0]).unwrap().hp=10;
    w.attack(&id,6,"burst",Instant::now()).unwrap();assert_eq!((w.players[&id].level,w.players[&id].exp),(2,5));
    assert_eq!((w.combat.monsters[&ids[1]].hp,w.combat.monsters[&ids[2]].hp),(5,5));assert_eq!(w.players[&id].mp,60);
}

#[test]
fn interrupted_multi_kill_recovers_rewards_and_mana_as_one_group() {
    let (mut w,a,ids)=arena(&[(1,-1),(1,0),(1,1)]);let (b,_)=w.login(Command::Register{protocol:PROTOCOL,name:"광역 복구".into()}).unwrap();let now=Instant::now();
    w.attack(&a,6,"basic",now).unwrap();let blocked_id=std::cmp::max(&a,&b);let blocked=w.root.join(format!("players/{blocked_id}.json.tmp"));fs::create_dir(&blocked).unwrap();
    assert!(w.attack(&b,6,"burst",now).is_err());assert_eq!((w.players[&a].exp,w.players[&b].exp,w.players[&b].mp),(0,0,50));assert!(ids.iter().all(|m|w.combat.monsters[m].hp==20));
    fs::remove_dir(blocked).unwrap();let recovered=World::load(&w.root).unwrap();assert_eq!((recovered.players[&a].exp,recovered.players[&b].exp,recovered.players[&b].mp),(9,21,40));
    let again=World::load(&w.root).unwrap();assert_eq!(again.players[&a].exp+again.players[&b].exp,30);
}

#[test]
fn old_visual_definitions_default_and_invalid_effect_is_rejected() {
    let w=fixture();let path=w.root.join("data/skills.json");let mut skills:serde_json::Value=load_json(&path).unwrap();
    for s in skills.as_array_mut().unwrap(){for key in ["motion","motion_ms","hit_effect"]{s.as_object_mut().unwrap().remove(key);}}
    fs::write(&path,serde_json::to_vec(&skills).unwrap()).unwrap();let loaded=World::load(&w.root).unwrap();assert_eq!(loaded.combat.skills["burst"].motion,"magic");assert_eq!(loaded.combat.skills["basic"].motion_ms,240);
    skills[0]["hit_effect"]=json!("../bad");fs::write(path,serde_json::to_vec(&skills).unwrap()).unwrap();assert!(World::load(&w.root).is_err());
}

#[test]
fn old_protocols_and_client_supplied_target_lists_are_rejected() {
    let mut w=fixture();for protocol in [1,2,3,4,5,6,7] {assert!(w.login(Command::Register{protocol,name:"구버전".into()}).is_err());}assert!(w.players.is_empty());
    assert!(serde_json::from_value::<Command>(json!({"type":"attack","skill_id":"burst","direction":6,"target_id":"sprout_0"})).is_err());
    assert!(matches!(serde_json::from_value::<Command>(json!({"type":"attack","skill_id":"basic","direction":6})).unwrap(),Command::Attack{direction:6,..}));
}

fn hint(step:u64,direction:u8,ms:u16)->PreviewPart {PreviewPart{step,direction,ms}}

#[test]
fn previews_are_immediate_validated_visuals_without_player_or_disk_mutation() {
    let mut w=fixture();let (id,_)=register(&mut w);w.npcs.clear();let (x,y)=w.players[&id].motion();
    let file=w.root.join(format!("players/{id}.json"));let bytes=fs::read(&file).unwrap();
    w.preview(&id,[x,y],0,35,&[hint(1,6,35)],true,6).unwrap();
    let s=w.state(&id,"");assert_eq!(s["self"]["relay"]["x"],x+175);assert_eq!(s["self"]["relay"]["lead_x"],x+475);
    assert_eq!(w.players[&id].motion(),(x,y));assert_eq!(fs::read(&file).unwrap(),bytes);
    let cmd=movement(&w,&id,1,vec![part(6,35)]);command(&mut w,&id,cmd).unwrap();
    w.preview(&id,[x+175,y],0,70,&[hint(2,2,35)],false,2).unwrap();
    let s=w.state(&id,"");assert_eq!(s["self"]["relay"]["y"],y+175);assert_eq!(s["self"]["relay"]["lead_y"],y+175);
    assert_eq!(w.players[&id].motion(),(x+175,y));
    w.clear_preview(&id);assert!(w.state(&id,"")["self"]["relay"].is_null());
}

#[test]
fn previews_reject_forgery_stale_history_speed_and_respawn_epochs_atomically() {
    let mut w=fixture();let (id,_)=register(&mut w);w.npcs.clear();let (x,y)=w.players[&id].motion();
    w.preview(&id,[x,y],0,35,&[hint(1,6,35)],true,6).unwrap();
    let before=w.state(&id,"")["self"]["relay"].clone();
    for (origin,epoch,elapsed,parts) in [([x+1,y],0,70,vec![hint(2,2,35)]),([x,y],1,35,vec![hint(1,6,35)]),
        ([x,y],0,35,vec![hint(1,6,35),hint(2,2,35)]),([x,y],0,70,vec![hint(1,2,35),hint(2,2,35)]),
        ([x,y],0,34,vec![hint(1,6,35)]),([x,y],0,635,vec![hint(2,6,600)]),([x,y],0,35,vec![]),
        ([x,y],0,70,vec![hint(0,6,35)]),([x,y],0,70,vec![hint(1,6,35),hint(1,2,35)])] {
        assert!(w.preview(&id,origin,epoch,elapsed,&parts,true,6).is_err());
        assert_eq!(w.state(&id,"")["self"]["relay"],before);
    }
    w.preview(&id,[x,y],0,35,&[hint(1,6,35)],true,6).unwrap();
    assert_eq!(w.state(&id,"")["self"]["relay"],before);
}

#[test]
fn previews_and_short_lead_respect_server_passages_and_npcs() {
    for npc in [false,true] {
        let mut w=fixture();let (id,_)=register(&mut w);let p=w.players[&id].position.clone();
        if !npc {w.npcs.clear();w.maps.get_mut(&p.map_id).unwrap().passages[p.y as usize][p.x as usize+1]=2;}
        let (x,y)=w.players[&id].motion();let d=if npc {2}else{6};
        w.preview(&id,[x,y],0,200,&[hint(1,d,200)],true,d).unwrap();
        let r=w.state(&id,"")["self"]["relay"].clone();
        assert_eq!(r[if npc {"y"}else{"x"}],if npc {y+495}else{x+495});
        assert_eq!(r[if npc {"lead_y"}else{"lead_x"}],if npc {y+495}else{x+495});
        assert_eq!(w.players[&id].motion(),(x,y));
    }
}

#[test]
fn failed_durable_move_retraces_preview_corners_and_stops_leading() {
    let mut w=fixture();let (id,_)=register(&mut w);w.npcs.clear();let (x,y)=w.players[&id].motion();
    w.preview(&id,[x,y],0,70,&[hint(1,6,35),hint(2,2,35)],true,2).unwrap();
    let file=w.root.join(format!("players/{id}.json"));let bytes=fs::read(&file).unwrap();fs::create_dir(file.with_extension("json.tmp")).unwrap();
    let mut ack=MoveAck::default();let mut time=Instant::now()-Duration::from_secs(1);let mut chat=time;
    let cmd=movement(&w,&id,1,vec![part(6,35),part(2,35)]);
    assert!(ack.process(&mut w,&id,cmd,&mut time,&mut chat).is_err());
    let r=w.state(&id,"")["self"]["relay"].clone();let path=r["path"].as_array().unwrap();let n=path.len();
    assert_eq!((path[n-2]["x"].clone(),path[n-2]["y"].clone()),(json!(x+175),json!(y)));
    assert_eq!((r["x"].clone(),r["y"].clone()),(json!(x),json!(y)));assert_eq!(r["moving"],false);
    assert_eq!(fs::read(file).unwrap(),bytes);assert_eq!(ack.seq,1);assert!(!ack.accepted);
}

#[test]
fn preview_history_coalesces_straights_preserves_turns_and_expires_lead() {
    let mut w=fixture();let (id,_)=register(&mut w);w.npcs.clear();let (x,y)=w.players[&id].motion();
    let parts:Vec<_>=(1..=30).map(|step|hint(step,6,8)).collect();
    w.preview(&id,[x,y],0,240,&parts,true,6).unwrap();
    assert_eq!(w.state(&id,"")["self"]["relay"]["path"].as_array().unwrap().len(),2);
    std::thread::sleep(Duration::from_millis(160));
    assert_eq!(w.state(&id,"")["self"]["relay"]["moving"],false);
    let mut parts=parts;parts.push(hint(31,2,8));w.preview(&id,[x,y],0,248,&parts,false,2).unwrap();
    assert_eq!(w.state(&id,"")["self"]["relay"]["path"].as_array().unwrap().len(),3);
}
