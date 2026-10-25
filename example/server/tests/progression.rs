#![cfg(windows)]
use lunetile_mmo_server::*;
use std::{fs,path::PathBuf,time::{Duration,Instant,SystemTime,UNIX_EPOCH}};
fn fixture()->World {
    let source=PathBuf::from(env!("CARGO_MANIFEST_DIR"));let root=source.join("target/test-data").join(format!("progress-{}-{}",std::process::id(),SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));
    fs::create_dir_all(root.join("data")).unwrap();
    for name in ["server","maps","items","npcs","growth","skills","monsters","progression"] {fs::copy(source.join(format!("data/{name}.json")),root.join(format!("data/{name}.json"))).unwrap();}
    World::load(&root).unwrap()
}
fn register(w:&mut World)->String {w.login(Command::Register{protocol:PROTOCOL,name:"성장 검사".into()}).unwrap().0}
fn act(w:&mut World,id:&str,action:&str,key:&str)->Result<String> {let mut t=Instant::now()-Duration::from_secs(2);let mut c=t;w.command(id,Command::Progress{action:action.into(),key:key.into()},&mut t,&mut c)}
#[test]
fn starter_gear_and_equipment_are_persistent_and_do_not_heal() {
    let mut w=fixture();let id=register(&mut w);assert_eq!(w.players[&id].progress.gear.len(),6);
    let gear=w.players[&id].progress.gear.iter().find(|(_,g)|g.definition=="body_1").unwrap().0.clone();
    act(&mut w,&id,"equip",&gear).unwrap();assert_eq!((w.players[&id].max_hp,w.players[&id].hp),(120,70));
    let loaded=World::load(&w.root).unwrap();assert_eq!(loaded.players[&id].progress.equipped["body"],gear);assert_eq!(loaded.players[&id].progress.gear.len(),6);
    act(&mut w,&id,"unequip","body").unwrap();assert_eq!((w.players[&id].max_hp,w.players[&id].hp),(100,70));
}
#[test]
fn equipped_weapon_definition_is_public_without_private_gear_and_only_after_save() {
    let mut w=fixture();let a=register(&mut w);let b=w.login(Command::Register{protocol:PROTOCOL,name:"무기 관찰자".into()}).unwrap().0;
    let gear=w.players[&a].progress.gear.iter().find(|(_,g)|g.definition=="weapon_1").unwrap().0.clone();
    assert!(w.state(&b,"")["players"].as_array().unwrap().iter().find(|p|p["id"]==a).unwrap()["weapon"].is_null());
    act(&mut w,&a,"equip",&gear).unwrap();let mut published=World::load(&w.root).unwrap();w.publish(&mut published);
    let state=published.state(&b,"");let seen=state["players"].as_array().unwrap().iter().find(|p|p["id"]==a).unwrap();
    assert_eq!(seen["weapon"],"weapon_1");for key in ["token","inventory","progress","gear","equipped"]{assert!(seen.get(key).is_none());}
    assert!(!seen.to_string().contains(&gear));
    let path=w.root.join("players");fs::rename(&path,w.root.join("held-players")).unwrap();fs::write(&path,b"blocked").unwrap();
    assert!(act(&mut w,&a,"unequip","weapon").is_err());assert_eq!(w.moving_public(&w.players[&a])["weapon"],"weapon_1");
    fs::remove_file(&path).unwrap();fs::rename(w.root.join("held-players"),&path).unwrap();act(&mut w,&a,"unequip","weapon").unwrap();w.publish(&mut published);
    assert!(published.moving_public(&published.players[&a])["weapon"].is_null());
    let saved:serde_json::Value=load_json(&path.join(format!("{a}.json"))).unwrap();assert!(saved.get("weapon").is_none());assert_eq!(saved["schema"],3);
}
#[test]
fn learned_skills_require_points_and_passives_cannot_be_cast_or_bound() {
    let mut w=fixture();let id=register(&mut w);
    assert!(w.attack(&id,6,"burst",Instant::now()).is_err());
    act(&mut w,&id,"learn","burst").unwrap();assert!(act(&mut w,&id,"learn","burst").is_err());
    act(&mut w,&id,"bind","burst").unwrap();w.attack(&id,6,"burst",Instant::now()).unwrap();
    assert!(act(&mut w,&id,"learn","mage_3").is_err());assert!(act(&mut w,&id,"bind","mage_3").is_err());
}
#[test]
fn advancement_enforces_level_family_and_town() {
    let mut w=fixture();let id=register(&mut w);assert!(act(&mut w,&id,"job","mage").is_err());
    {let p=w.players.get_mut(&id).unwrap();p.level=5;p.progress.skill_points=5;}
    act(&mut w,&id,"job","mage").unwrap();assert!(act(&mut w,&id,"job","warrior").is_err());assert!(act(&mut w,&id,"job","mage2").is_err());
    {let p=w.players.get_mut(&id).unwrap();p.level=20;p.progress.skill_points=20;}
    assert!(act(&mut w,&id,"job","warrior2").is_err());act(&mut w,&id,"job","mage2").unwrap();
}
#[test]
fn safe_enhancement_consumes_resources_and_preserves_failed_gear() {
    let mut w=fixture();let id=register(&mut w);let gear=w.players[&id].progress.gear.keys().next().unwrap().clone();
    {let p=w.players.get_mut(&id).unwrap();p.progress.coins=1000;p.inventory.insert("upgrade_stone".into(),2);}
    act(&mut w,&id,"enhance",&gear).unwrap();assert_eq!(w.players[&id].progress.gear[&gear].enhancement,1);
    w.progression.as_mut().unwrap().enhancement_chances[1]=0;act(&mut w,&id,"enhance",&gear).unwrap();
    assert_eq!(w.players[&id].progress.gear[&gear].enhancement,1);assert_eq!(w.players[&id].progress.coins,700);assert!(!w.players[&id].inventory.contains_key("upgrade_stone"));
}
#[test]
fn failed_save_does_not_spend_skill_points() {
    let mut w=fixture();let id=register(&mut w);let directory=w.root.join("players");let backup=w.root.join("players-held");
    fs::rename(&directory,&backup).unwrap();fs::write(&directory,b"failure").unwrap();
    assert!(act(&mut w,&id,"learn","burst").is_err());assert_eq!(w.players[&id].progress.skill_points,1);assert!(w.players[&id].progress.skills.is_empty());
    fs::remove_file(&directory).unwrap();fs::rename(backup,directory).unwrap();
}
#[test]
fn old_account_migrates_once_with_original_backup_and_burst() {
    let mut w=fixture();let id=register(&mut w);let path=w.root.join(format!("players/{id}.json"));
    let mut value:serde_json::Value=serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();value.as_object_mut().unwrap().remove("progress");value["schema"]=2.into();
    let original=serde_json::to_vec(&value).unwrap();fs::write(&path,&original).unwrap();
    let loaded=World::load(&w.root).unwrap();let p=&loaded.players[&id];assert_eq!(p.progress.skills["burst"],1);assert_eq!(p.progress.skill_points,0);assert_eq!(p.progress.gear.len(),6);
    assert_eq!(fs::read(path.with_extension("json.pre-v7.bak")).unwrap(),original);
    let again=World::load(&w.root).unwrap();assert_eq!(again.players[&id].progress.gear.len(),6);
}

fn social(w:&mut World,id:&str,action:&str,key:&str,amount:u32,revision:u64)->Result<String> {
    let mut t=Instant::now()-Duration::from_secs(2);let mut c=t;
    w.command(id,Command::Social{action:action.into(),key:key.into(),amount,text:"검증 길드".into(),revision},&mut t,&mut c)
}
fn pair()->(World,String,String) {let mut w=fixture();let a=register(&mut w);let b=w.login(Command::Register{protocol:PROTOCOL,name:"협동 검사".into()}).unwrap().0;(w,a,b)}
#[test]
fn trade_requires_matching_confirmations_and_preserves_gear_instance() {
    let (mut w,a,b)=pair();let gear=w.players[&a].progress.gear.keys().next().unwrap().clone();
    w.players.get_mut(&a).unwrap().progress.gear.get_mut(&gear).unwrap().enhancement=2;
    social(&mut w,&a,"trade_invite",&b,0,0).unwrap();social(&mut w,&b,"accept","",0,0).unwrap();
    social(&mut w,&a,"trade_gear",&gear,1,0).unwrap();let rev=w.social.trades[&a].revision;
    social(&mut w,&a,"trade_confirm","",0,rev).unwrap();social(&mut w,&b,"trade_item","potion",1,0).unwrap();
    assert!(social(&mut w,&a,"trade_confirm","",0,rev).is_err());let rev=w.social.trades[&a].revision;
    social(&mut w,&b,"trade_confirm","",0,rev).unwrap();assert!(w.players[&a].progress.gear.contains_key(&gear));
    social(&mut w,&a,"trade_confirm","",0,rev).unwrap();assert!(!w.players[&a].progress.gear.contains_key(&gear));assert_eq!(w.players[&b].progress.gear[&gear].enhancement,2);
    assert_eq!(w.players[&a].inventory["potion"],3);assert_eq!(w.players[&b].inventory["potion"],1);
    let loaded=World::load(&w.root).unwrap();assert_eq!(loaded.players[&b].progress.gear[&gear].enhancement,2);
}
#[test]
fn trade_failure_or_disconnect_never_takes_an_offer() {
    let (mut w,a,b)=pair();social(&mut w,&a,"trade_invite",&b,0,0).unwrap();social(&mut w,&b,"accept","",0,0).unwrap();
    social(&mut w,&a,"trade_item","potion",2,0).unwrap();let rev=w.social.trades[&a].revision;social(&mut w,&a,"trade_confirm","",0,rev).unwrap();
    fs::write(w.root.join("transactions"),b"fail").unwrap();assert!(social(&mut w,&b,"trade_confirm","",0,rev).is_err());
    assert_eq!(w.players[&a].inventory["potion"],2);assert_eq!(w.players[&b].inventory["potion"],2);
    w.online.remove(&a);w.social_tick();assert!(w.social.trades.is_empty());
}
#[test]
fn party_consent_and_guild_membership_survive_the_right_lifetimes() {
    let (mut w,a,b)=pair();social(&mut w,&a,"party_create","",0,0).unwrap();social(&mut w,&a,"party_invite",&b,0,0).unwrap();
    assert_eq!(w.social.parties[&a].len(),1);social(&mut w,&b,"accept","",0,0).unwrap();assert_eq!(w.social.parties[&a].len(),2);
    social(&mut w,&a,"party_leave","",0,0).unwrap();assert_eq!(w.social.parties[&b],vec![b.clone()]);
    w.players.get_mut(&a).unwrap().progress.coins=500;social(&mut w,&a,"guild_create","",0,0).unwrap();social(&mut w,&a,"guild_invite",&b,0,0).unwrap();social(&mut w,&b,"accept","",0,0).unwrap();
    let loaded=World::load(&w.root).unwrap();assert_eq!(loaded.players[&b].progress.guild.as_deref(),Some(a.as_str()));assert!(loaded.social.parties.is_empty());
    assert!(social(&mut w,&b,"guild_disband","",0,0).is_err());social(&mut w,&a,"guild_disband","",0,0).unwrap();assert!(w.players[&b].progress.guild.is_none());
}
#[test]
fn storage_moves_equipment_without_losing_enhancement_and_shop_is_atomic() {
    let mut w=fixture();let id=register(&mut w);
    w.services=Some(services::Services{quests:vec![],portals:vec![],shop:[("potion".into(),20)].into(),loot:vec![]});
    let key=w.players[&id].progress.gear.keys().next().unwrap().clone();w.players.get_mut(&id).unwrap().progress.gear.get_mut(&key).unwrap().enhancement=3;
    w.service_command(&id,"store_gear",&key,1).unwrap();assert!(!w.players[&id].progress.gear.contains_key(&key));
    w.service_command(&id,"withdraw_gear",&key,1).unwrap();assert_eq!(w.players[&id].progress.gear[&key].enhancement,3);
    w.players.get_mut(&id).unwrap().progress.coins=100;assert!(w.service_command(&id,"buy","potion",100).is_err());assert_eq!(w.players[&id].progress.coins,100);
    w.service_command(&id,"buy","potion",2).unwrap();assert_eq!(w.players[&id].inventory["potion"],4);assert_eq!(w.players[&id].progress.coins,60);
}
fn with_services()->World {let mut w=fixture();fs::copy(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("data/services.json"),w.root.join("data/services.json")).unwrap();w.services=services::Services::load(&w.root).unwrap();w.validate_services().unwrap();w}
#[test]
fn ten_quests_are_ordered_once_only_and_portals_enforce_map_and_level() {
    let mut w=with_services();let id=register(&mut w);assert_eq!(w.services.as_ref().unwrap().quests.len(),10);
    assert!(w.service_command(&id,"quest_accept","quest_02",1).is_err());
    let quests=w.services.as_ref().unwrap().quests.clone();
    for q in quests {
        {let p=w.players.get_mut(&id).unwrap();p.level=30;p.exp=0;p.progress.skill_points=30;}
        w.service_command(&id,"quest_accept",&q.id,1).unwrap();assert!(w.service_command(&id,"quest_claim",&q.id,1).is_err());
        w.players.get_mut(&id).unwrap().progress.quests.insert(q.id.clone(),q.count);
        w.service_command(&id,"quest_claim",&q.id,1).unwrap();let coins=w.players[&id].progress.coins;
        assert!(w.service_command(&id,"quest_claim",&q.id,1).is_err());assert_eq!(w.players[&id].progress.coins,coins);
    }
    let portal=w.services.as_ref().unwrap().portals.iter().find(|p|p.to.map_id==5).unwrap().clone();
    assert!(w.service_command(&id,"portal",&portal.id,1).is_err());
    {let p=w.players.get_mut(&id).unwrap();p.position=portal.from.clone();p.level=1;p.progress.skill_points=1;}
    assert!(w.service_command(&id,"portal",&portal.id,1).is_err());
    {let p=w.players.get_mut(&id).unwrap();p.level=30;p.progress.skill_points=30;}
    let epoch=w.state(&id,"")["self"]["motion"]["epoch"].as_u64().unwrap();
    w.service_command(&id,"portal",&portal.id,1).unwrap();assert_eq!(w.players[&id].position.map_id,5);
    assert_eq!(w.state(&id,"")["self"]["motion"]["epoch"].as_u64().unwrap(),epoch+1);
    let loaded=World::load(&w.root).unwrap();assert_eq!(loaded.players[&id].progress.completed.len(),10);assert_eq!(loaded.players[&id].position.map_id,5);
}
#[test]
fn party_kill_shares_exact_exp_and_quest_credit_with_nearby_living_members() {
    let mut w=with_services();let a=register(&mut w);let b=w.login(Command::Register{protocol:PROTOCOL,name:"파티 보상".into()}).unwrap().0;
    social(&mut w,&a,"party_create","",0,0).unwrap();social(&mut w,&a,"party_invite",&b,0,0).unwrap();social(&mut w,&b,"accept","",0,0).unwrap();
    for id in [&a,&b]{w.service_command(id,"quest_accept","quest_01",1).unwrap();}
    let p=w.players[&a].position.clone();w.combat.monsters.retain(|id,_|id=="sprout_0");let m=w.combat.monsters.get_mut("sprout_0").unwrap();m.hp=10;m.position=Position{map_id:p.map_id,x:p.x+1,y:p.y};m.origin=m.position.clone();
    let loot=w.services.as_mut().unwrap().loot.iter_mut().find(|l|l.monster=="sprout").unwrap();loot.gear_chance=100;loot.material_chance=100;
    w.attack(&a,6,"basic",Instant::now()).unwrap();
    assert_eq!((w.players[&a].exp,w.players[&b].exp),(5,5));
    for id in [&a,&b]{assert_eq!(w.players[id].progress.quests["quest_01"],1);}
    assert_eq!(w.players[&a].progress.gear.len(),7);assert_eq!(w.players[&a].inventory["upgrade_stone"],1);
    assert_eq!(w.players[&b].progress.gear.len(),6);
    let mut updated=w.players[&b].clone();updated.hp=0;w.players.insert(b.clone(),updated);assert_eq!(w.reward_members(&a,&p),vec![a]);
}
#[test]
fn skill_cycles_and_overlarge_saved_enhancement_fail_without_overflow() {
    let mut w=fixture();let id=register(&mut w);let path=w.root.join(format!("players/{id}.json"));
    let mut p=w.players[&id].clone();p.progress.gear.values_mut().next().unwrap().enhancement=u32::MAX;let key=p.progress.gear.keys().next().unwrap().clone();let slot=w.progression.as_ref().unwrap().equipment(&p.progress.gear[&key].definition).unwrap().slot.clone();p.progress.equipped.insert(slot,key);
    fs::write(&path,serde_json::to_vec(&p).unwrap()).unwrap();assert!(World::load(&w.root).is_err());
    let mut rules=w.progression.take().unwrap();rules.skills[0].requires=Some(rules.skills[1].id.clone());rules.skills[1].requires=Some(rules.skills[0].id.clone());
    fs::write(w.root.join("data/progression.json"),serde_json::to_vec(&rules).unwrap()).unwrap();assert!(progression::Rules::load(&w.root).is_err());
}
#[test]
fn recovery_commits_enhanced_equipment_transfer_exactly_once() {
    let (w,a,b)=pair();let mut pa=w.players[&a].clone();let mut pb=w.players[&b].clone();let key=pa.progress.gear.keys().next().unwrap().clone();let mut gear=pa.progress.gear.remove(&key).unwrap();gear.enhancement=4;pb.progress.storage_gear.insert(key.clone(),gear);
    let blocked=w.root.join(format!("players/{b}.json"));fs::remove_file(&blocked).unwrap();fs::create_dir(&blocked).unwrap();
    fs::create_dir_all(w.root.join("transactions")).unwrap();fs::write(w.root.join("transactions/pending.json"),serde_json::to_vec(&[pa.clone(),pb]).unwrap()).unwrap();fs::write(w.root.join(format!("players/{a}.json")),serde_json::to_vec(&pa).unwrap()).unwrap();
    assert!(World::load(&w.root).is_err());assert!(w.root.join("transactions/pending.json").exists());fs::remove_dir(&blocked).unwrap();
    let loaded=World::load(&w.root).unwrap();assert!(!loaded.players[&a].progress.gear.contains_key(&key));assert_eq!(loaded.players[&b].progress.storage_gear[&key].enhancement,4);
    let again=World::load(&w.root).unwrap();assert_eq!(again.players[&b].progress.storage_gear.len(),1);assert!(!w.root.join("transactions/pending.json").exists());
}
#[test]
fn four_families_advance_and_ranged_skills_only_hit_the_forward_line() {
    for job in ["warrior","mage","archer","rogue"] {
        let mut w=fixture();let id=register(&mut w);w.npcs.clear();
        {let p=w.players.get_mut(&id).unwrap();p.level=25;p.progress.skill_points=25;}
        act(&mut w,&id,"job",job).unwrap();act(&mut w,&id,"job",&format!("{job}2")).unwrap();
        for n in [1,2,3]{act(&mut w,&id,"learn",&format!("{job}_{n}")).unwrap();}
        let p=w.players[&id].position.clone();let template=w.combat.monsters["sprout_0"].clone();w.combat.monsters.clear();
        for (i,(x,y)) in [(1,0),(3,0),(1,1),(-1,0)].into_iter().enumerate() {let mut m=template.clone();m.id=format!("probe_{i}");m.hp=1000;m.position=Position{map_id:1,x:p.x+x,y:p.y+y};m.origin=m.position.clone();w.combat.monsters.insert(m.id.clone(),m);}
        w.attack(&id,6,&format!("{job}_2"),Instant::now()).unwrap();
        assert!(w.combat.monsters["probe_0"].hp<1000&&w.combat.monsters["probe_1"].hp<1000);assert_eq!(w.combat.monsters["probe_3"].hp,1000);
        assert_eq!(w.combat.monsters["probe_2"].hp==1000,["mage","archer"].contains(&job));
        let stats=w.player_stats(&w.players[&id]);match job {"warrior"=>assert_eq!(stats.hp,600),"mage"=>assert_eq!(stats.regen,7),"archer"=>assert_eq!(stats.attack,60),_=>assert_eq!(stats.defense,1)}
    }
}
