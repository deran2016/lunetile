use super::*;

#[derive(Clone,Default,Serialize,Deserialize)]
#[serde(default,deny_unknown_fields)]
pub struct Bindings {pub cast:Option<String>,pub hit:Option<String>,pub explosion:Option<String>}
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Preset {pub id:String,pub layers:Vec<Layer>}
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Layer {
    pub shape:String,pub count:u32,pub emit_ms:u32,pub delay_ms:u32,pub life_ms:[u32;2],
    pub speed:[f32;2],pub angle:[f32;2],pub gravity:[f32;2],pub spread:f32,pub size:[f32;2],pub spin:f32,
    pub colors:Vec<[u8;3]>,pub blend:u8,pub z:u32,pub directional:bool,
}
fn pair(v:&[f32;2],min:f32,max:f32,ordered:bool)->bool {v.iter().all(|n|n.is_finite()&&*n>=min&&*n<=max)&&(!ordered||v[0]<=v[1])}
pub fn load(root:&Path)->Result<Vec<Preset>> {
    let path=root.join("data/particles.json");
    let presets:Vec<Preset>=if path.exists(){load_json(&path)?}else{serde_json::from_str(include_str!("../data/particles.json"))?};
    if presets.len()>16{return Err("At most 16 particle presets".into());}
    let mut ids=BTreeSet::new();
    for p in &presets {
        if !valid_id(&p.id)||!ids.insert(&p.id)||p.layers.is_empty()||p.layers.len()>4{return Err("Invalid particle preset".into());}
        let mut total=0;
        for (index,l) in p.layers.iter().enumerate() {
            total+=l.count.min(97);
            if !["glow","spark","smoke","ring","drop","flame"].contains(&l.shape.as_str())||!(1..=48).contains(&l.count)
                ||l.emit_ms>1000||l.delay_ms>1000||l.life_ms[0]<50||l.life_ms[1]>3000||l.life_ms[0]>l.life_ms[1]
                ||!pair(&l.speed,0.,240.,true)||!pair(&l.angle,-720.,720.,true)||!pair(&l.gravity,-500.,500.,false)
                ||!pair(&l.size,0.05,4.0,false)||!l.spread.is_finite()||!(0.0..=96.0).contains(&l.spread)
                ||!l.spin.is_finite()||!(-720.0..=720.0).contains(&l.spin)||l.colors.is_empty()||l.colors.len()>4||l.blend>1||l.z>1200 {
                return Err(format!("Invalid particle layer {} in {}",index+1,p.id).into());
            }
        }
        if total>96{return Err("At most 96 particles per preset".into());}
    }
    Ok(presets)
}
