use std::{collections::BTreeMap,fs::OpenOptions,io::Write,path::Path,sync::{Mutex,OnceLock},time::Instant};
#[derive(Default)]
struct Timing {count:u64,sum:u128,max:u64,bins:BTreeMap<u64,u64>}
static DATA:OnceLock<Mutex<BTreeMap<&'static str,Timing>>>=OnceLock::new();
static GAUGES:OnceLock<Mutex<BTreeMap<&'static str,(u64,u64)>>>=OnceLock::new();
pub fn enable(){DATA.get_or_init(Mutex::default);}
pub fn record(name:&'static str,micros:u64) {
 if let Some(data)=DATA.get(){if let Ok(mut data)=data.lock(){let t=data.entry(name).or_default();t.count+=1;t.sum+=u128::from(micros);t.max=t.max.max(micros);*t.bins.entry((micros/1000).min(2000)).or_default()+=1;}}
}
pub fn elapsed(name:&'static str,began:Instant){record(name,began.elapsed().as_micros() as u64);}
pub fn gauge(name:&'static str,value:u64){if DATA.get().is_some(){if let Ok(mut data)=GAUGES.get_or_init(Mutex::default).lock(){let v=data.entry(name).or_default();v.0=value;v.1=v.1.max(value);}}}
pub fn write(path:&Path)->std::io::Result<()> {
 let Some(data)=DATA.get() else{return Ok(());};let data=data.lock().map_err(|_|std::io::Error::other("metrics lock"))?;
 let mut values:BTreeMap<_,_>=data.iter().map(|(name,t)|{
  let percentile=|p:u64|{let mut n=0;for (ms,count) in &t.bins{n+=count;if n*100>=t.count*p{return ms+1;}}0};
  (*name,serde_json::json!({"count":t.count,"mean_us":if t.count==0{0}else{(t.sum/u128::from(t.count))as u64},"max_us":t.max,"p95_ms":percentile(95),"p99_ms":percentile(99)}))
 }).collect();
 if let Some(gauges)=GAUGES.get(){values.insert("_gauges",serde_json::to_value(&*gauges.lock().map_err(|_|std::io::Error::other("gauge lock"))?)?);}
 let mut f=OpenOptions::new().create(true).append(true).open(path)?;serde_json::to_writer(&mut f,&values)?;f.write_all(b"\n")
}
