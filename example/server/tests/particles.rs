#![cfg(windows)]
use lunetile_mmo_server::*;
use serde_json::json;
use std::{fs,path::PathBuf,time::{Duration,Instant,SystemTime,UNIX_EPOCH}};
fn fixture()->(World,String) {
    let source=PathBuf::from(env!("CARGO_MANIFEST_DIR"));let root=source.join("target/test-data").join(format!("particles-{}-{}",std::process::id(),SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));
    fs::create_dir_all(root.join("data")).unwrap();
    for name in ["server","maps","items","npcs","growth","skills","monsters","progression","services","particles"]{fs::copy(source.join(format!("data/{name}.json")),root.join(format!("data/{name}.json"))).unwrap();}
    let mut w=World::load(&root).unwrap();let id=w.login(Command::Register{protocol:PROTOCOL,name:"파티클 검사".into()}).unwrap().0;(w,id)
}
#[test]
fn missing_preset_file_uses_defaults_without_rewriting_accounts() {
    let (w,id)=fixture();let player=w.root.join(format!("players/{id}.json"));let before=fs::read(&player).unwrap();fs::remove_file(w.root.join("data/particles.json")).unwrap();
    let loaded=World::load(&w.root).unwrap();assert_eq!(loaded.combat.particles.len(),3);assert_eq!(fs::read(player).unwrap(),before);
}
#[test]
fn malformed_layers_and_unknown_skill_references_fail_without_data_loss() {
    let (w,id)=fixture();let player=w.root.join(format!("players/{id}.json"));let before=fs::read(&player).unwrap();let path=w.root.join("data/particles.json");let original:serde_json::Value=load_json(&path).unwrap();
    for (key,value) in [("count",json!(49)),("shape",json!("../bad")),("life_ms",json!([0,100])),("colors",json!([[256,0,0]])),("gravity",json!([501,0])),("size",json!([0,1])),("blend",json!(2))] {
        let mut bad=original.clone();bad[0]["layers"][0][key]=value;fs::write(&path,serde_json::to_vec(&bad).unwrap()).unwrap();assert!(World::load(&w.root).is_err());assert_eq!(fs::read(&player).unwrap(),before);
    }
    fs::write(&path,serde_json::to_vec(&original).unwrap()).unwrap();let skill_path=w.root.join("data/skills.json");let mut skills:serde_json::Value=load_json(&skill_path).unwrap();
    let oversized=vec![skills[0].clone();65];fs::write(&skill_path,serde_json::to_vec(&oversized).unwrap()).unwrap();assert!(World::load(&w.root).is_err());
    skills[1]["particles"]["cast"]=json!("unknown");fs::write(skill_path,serde_json::to_vec(&skills).unwrap()).unwrap();assert!(World::load(&w.root).is_err());assert_eq!(fs::read(player).unwrap(),before);
}
#[test]
fn approved_events_carry_phase_presets_without_changing_damage_or_mana_rules() {
    let (mut w,id)=fixture();w.progress_command(&id,"learn","burst").unwrap();w.npcs.clear();let origin=w.players[&id].position.clone();
    let template=w.combat.monsters["sprout_0"].clone();w.combat.monsters.clear();let mut m=template;m.id="probe".into();m.hp=100;m.position=Position{map_id:1,x:origin.x+1,y:origin.y};w.combat.monsters.insert(m.id.clone(),m);
    let now=Instant::now();w.attack(&id,6,"burst",now).unwrap();let state=w.state(&id,"");assert_eq!(state["particle_presets"].as_array().unwrap().len(),3);
    let events=state["events"].as_array().unwrap();assert!(events.iter().any(|e|e["kind"]=="attack"&&e["particles"]=="light"));assert!(events.iter().any(|e|e["kind"]=="damage"&&e["particles"]=="light"));assert_eq!(w.players[&id].mp,40);assert_eq!(w.combat.monsters["probe"].hp,75);
    let (mut w,id)=fixture();w.progress_command(&id,"learn","grenade").unwrap();let now=Instant::now();w.attack(&id,6,"grenade",now).unwrap();w.tick(now+Duration::from_secs(1)).unwrap();assert!(w.state(&id,"")["events"].as_array().unwrap().iter().any(|e|e["kind"]=="explosion"&&e["particles"]=="fire"));
}
#[test]
fn elemental_skills_require_learning_spend_separate_mana_and_survive_reload() {
    let (mut w,id)=fixture();let now=Instant::now();
    for skill in ["fire_wave","light_wave","water_wave"] {
        assert!(w.attack(&id,6,skill,now).is_err());assert!(w.progress_command(&id,"bind",skill).is_err());
        let rule=w.progression.as_ref().unwrap().skill(skill).unwrap();
        assert_eq!((rule.job.as_str(),rule.level,rule.max_rank),("beginner",1,5));assert!(!rule.passive);
        for job in progression::JOBS {assert!(progression::job_matches(job,&rule.job));}
    }
    let mut p=w.players[&id].clone();p.level=3;p.progress.skill_points=3;w.refresh_resources(&mut p,true);w.players.insert(id.clone(),p);
    w.npcs.clear();let origin=w.players[&id].position.clone();let mut mob=w.combat.monsters["sprout_0"].clone();mob.id="probe".into();mob.hp=1000;mob.position=Position{map_id:1,x:origin.x+1,y:origin.y};
    w.combat.monsters.clear();w.combat.monsters.insert(mob.id.clone(),mob);
    let mut expected_mp=w.players[&id].mp;let mut expected_hp=1000;
    for (skill,preset,cost) in [("fire_wave","fire",10),("light_wave","light",10),("water_wave","water",8)] {
        w.progress_command(&id,"learn",skill).unwrap();w.progress_command(&id,"bind",skill).unwrap();
        w.attack(&id,6,skill,now).unwrap();expected_mp-=cost;expected_hp-=w.player_stats(&w.players[&id]).attack+w.combat.skills[skill].bonus;
        assert_eq!(w.players[&id].mp,expected_mp);assert_eq!(w.combat.monsters["probe"].hp,expected_hp);
        assert!(w.attack(&id,6,skill,now).is_err());assert_eq!(w.players[&id].mp,expected_mp);
        let state=w.state(&id,"");let events=state["events"].as_array().unwrap();
        assert!(events.iter().any(|e|e["kind"]=="attack"&&e["skill_id"]==skill&&e["particles"]==preset));
        assert!(events.iter().any(|e|e["kind"]=="damage"&&e["target"]=="probe"&&e["particles"]==preset));
    }
    assert_eq!(w.players[&id].progress.skill_points,0);assert!(w.progress_command(&id,"learn","fire_wave").is_err());
    let loaded=World::load(&w.root).unwrap();let p=&loaded.players[&id];assert_eq!(p.progress.quick_skill,"water_wave");
    for skill in ["fire_wave","light_wave","water_wave"] {assert_eq!(p.progress.skills[skill],1);}
}
