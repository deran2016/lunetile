#![cfg(windows)]
use lunetile_mmo_server::*;
use std::{collections::{BTreeMap,BTreeSet},fs,path::PathBuf,time::{Instant,Duration,SystemTime,UNIX_EPOCH}};
fn fixture()->(World,String,String){
 let source=PathBuf::from(env!("CARGO_MANIFEST_DIR"));let root=source.join("target/test-data").join(format!("snapshot-{}-{}",std::process::id(),SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));fs::create_dir_all(root.join("data")).unwrap();
 for name in ["server","maps","items","npcs","growth","skills","monsters","progression","services","particles"]{fs::copy(source.join(format!("data/{name}.json")),root.join(format!("data/{name}.json"))).unwrap();}
 let mut w=World::load(&root).unwrap();let a=w.login(Command::Register{protocol:PROTOCOL,name:"snapshot A".into()}).unwrap().0;let b=w.login(Command::Register{protocol:PROTOCOL,name:"snapshot B".into()}).unwrap().0;(w,a,b)
}
#[test]
fn snapshots_exclude_catalog_and_other_private_data_and_wait_for_commit(){
 let(mut w,a,b)=fixture();let mut p=publishing::Published::new(&w);let before=serde_json::to_value(p.view(&a).unwrap().response(String::new()).unwrap()).unwrap();
 for key in ["items","skills","progression","services","particle_presets"]{assert!(before.get(key).is_none());assert!(p.catalog.get(key).is_some());}
 let text=before.to_string();assert!(!text.contains(&w.players[&a].token)&&!text.contains(&w.players[&b].token));
 for gear in w.players[&b].progress.gear.keys(){assert!(!text.contains(gear));}
 storage::begin(&w.root);w.progress_command(&a,"learn","light_wave").unwrap();let records=storage::take();
 let uncommitted=serde_json::to_value(p.view(&a).unwrap().response(String::new()).unwrap()).unwrap();assert!(uncommitted["progress"]["skills"].get("light_wave").is_none());
 let store=storage::Store::start(&w.root).unwrap();store.commit(records).unwrap();p.commit(&w,&BTreeSet::from([a.clone()]));let committed=serde_json::to_value(p.view(&a).unwrap().response(String::new()).unwrap()).unwrap();assert_eq!(committed["progress"]["skills"]["light_wave"],1);store.finish().unwrap();
}
#[test]
fn path_deltas_send_each_corner_once_and_keep_full_self_reconciliation(){
 let(mut w,a,_)=fixture();w.npcs.clear();let mut last=Instant::now()-Duration::from_secs(1);w.move_parts(&a,&[MovePart{direction:6,ms:100}],&mut last).unwrap();let mut p=publishing::Published::new(&w);let mut cursors=BTreeMap::new();
 let mut first=p.view(&a).unwrap().response(String::new()).unwrap();first.trim_paths(&mut cursors);let first=serde_json::to_value(first).unwrap();let id=first["players"].as_array().unwrap().iter().position(|v|v["id"]==a).unwrap();assert!(!first["players"][id]["motion"]["path"].as_array().unwrap().is_empty());
 let mut repeat=p.view(&a).unwrap().response(String::new()).unwrap();repeat.trim_paths(&mut cursors);let repeat=serde_json::to_value(repeat).unwrap();assert!(repeat["players"][id]["motion"]["path"].as_array().unwrap().is_empty());assert!(!repeat["self"]["motion"]["path"].as_array().unwrap().is_empty());
 w.move_parts(&a,&[MovePart{direction:2,ms:100}],&mut last).unwrap();p.commit(&w,&BTreeSet::from([a.clone()]));let mut next=p.view(&a).unwrap().response(String::new()).unwrap();next.trim_paths(&mut cursors);let next=serde_json::to_value(next).unwrap();assert_eq!(next["players"][id]["motion"]["path"].as_array().unwrap().len(),1);
}
#[test]
fn event_deltas_do_not_repeat_and_backlog_loss_requires_resynchronization(){
 let(mut w,a,_)=fixture();for _ in 0..260{w.emit(1,None,serde_json::json!({"kind":"test"}));}
 let p=publishing::Published::new(&w);assert!(p.view(&a).unwrap().response_since(String::new(),0).is_err());
 let welcome=serde_json::to_value(p.view(&a).unwrap().response(String::new()).unwrap()).unwrap();assert!(welcome["events"].as_array().unwrap().is_empty());
 let current=welcome["event_seq"].as_u64().unwrap();let next=serde_json::to_value(p.view(&a).unwrap().response_since(String::new(),current-1).unwrap()).unwrap();assert_eq!(next["events"].as_array().unwrap().len(),1);
}
