use super::*;

pub const SLOTS: [&str;6] = ["weapon","shield","head","body","feet","accessory"];
pub const JOBS: [&str;9] = ["beginner","warrior","mage","archer","rogue","warrior2","mage2","archer2","rogue2"];

#[derive(Clone,Default,Serialize,Deserialize)]
#[serde(default,deny_unknown_fields)]
pub struct Bonuses {pub hp:u32,pub mp:u32,pub attack:u32,pub defense:u32,pub regen:u32}
impl Bonuses {
    fn valid(&self)->bool {[self.hp,self.mp,self.attack,self.defense,self.regen].iter().all(|v|*v<=10_000)}
    fn add(&mut self,other:&Self,n:u32) {self.hp+=other.hp*n;self.mp+=other.mp*n;self.attack+=other.attack*n;self.defense+=other.defense*n;self.regen+=other.regen*n;}
}
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EquipmentDef {pub id:String,pub name:String,pub description:String,pub icon:String,pub slot:String,pub job:String,pub level:u32,pub bonus:Bonuses,pub enhancement:Bonuses,pub price:u32}
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SkillRule {pub id:String,pub job:String,pub level:u32,pub max_rank:u32,pub requires:Option<String>,pub damage_per_rank:u32,pub passive:bool,pub bonus:Bonuses,pub shape:String}
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Rules {
    pub equipment:Vec<EquipmentDef>,pub skills:Vec<SkillRule>,pub starter_equipment:Vec<String>,
    pub enhancement_costs:Vec<u32>,pub enhancement_chances:Vec<u32>,pub enhancement_material:String,
}
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Gear {pub definition:String,pub enhancement:u32}
#[derive(Clone,Serialize,Deserialize)]
#[serde(default,deny_unknown_fields)]
pub struct Progress {
    pub initialized:bool,pub job:String,pub coins:u32,pub skill_points:u32,pub skills:BTreeMap<String,u32>,pub quick_skill:String,
    pub gear:BTreeMap<String,Gear>,pub equipped:BTreeMap<String,String>,pub storage_gear:BTreeMap<String,Gear>,pub storage:BTreeMap<String,u32>,pub storage_coins:u32,
    pub quests:BTreeMap<String,u32>,pub completed:BTreeSet<String>,pub guild:Option<String>,pub guild_name:String,
}
impl Default for Progress {
    fn default()->Self {Self {initialized:false,job:"beginner".into(),coins:0,skill_points:0,skills:BTreeMap::new(),quick_skill:"burst".into(),gear:BTreeMap::new(),equipped:BTreeMap::new(),storage_gear:BTreeMap::new(),storage:BTreeMap::new(),storage_coins:0,quests:BTreeMap::new(),completed:BTreeSet::new(),guild:None,guild_name:String::new()}}
}
impl Rules {
    pub fn load(root:&Path)->Result<Option<Self>> {
        let path=root.join("data/progression.json");if !path.exists(){return Ok(None);}
        let rules:Self=load_json(&path)?;
        if rules.equipment.len()>128 || rules.skills.len()>64 || rules.enhancement_costs.is_empty() || rules.enhancement_costs.len()>10
            || rules.enhancement_costs.len()!=rules.enhancement_chances.len() || rules.enhancement_costs.iter().any(|n|*n==0||*n>1_000_000)
            || rules.enhancement_chances.iter().any(|n|*n>100) || !valid_id(&rules.enhancement_material) {return Err("Invalid progression rules".into());}
        let mut ids=BTreeSet::new();
        for e in &rules.equipment {
            if !valid_id(&e.id)||!ids.insert(&e.id)||!text_ok(&e.name,32)||!text_ok(&e.description,200)||!asset_ok(&e.icon)
                ||!SLOTS.contains(&e.slot.as_str())||!JOBS.contains(&e.job.as_str())||!(1..=30).contains(&e.level)||!e.bonus.valid()||!e.enhancement.valid()||e.price>1_000_000 {return Err("Invalid equipment definition".into());}
        }
        if rules.starter_equipment.len()!=6 || rules.starter_equipment.iter().any(|id|!ids.contains(id)) {return Err("Invalid starter equipment".into());}
        let slots:BTreeSet<_>=rules.starter_equipment.iter().map(|id|rules.equipment(id).unwrap().slot.as_str()).collect();
        if slots.len()!=6{return Err("Starter equipment must cover all six slots".into());}
        let mut skills=BTreeSet::new();
        for s in &rules.skills {
            if !valid_id(&s.id)||!skills.insert(&s.id)||!JOBS.contains(&s.job.as_str())||!(1..=30).contains(&s.level)
                ||!(1..=5).contains(&s.max_rank)||s.damage_per_rank>1000||!s.bonus.valid()||!["fan","line","passive","throw"].contains(&s.shape.as_str())
                ||s.passive!=(s.shape=="passive") {return Err("Invalid skill progression".into());}
        }
        for s in &rules.skills {if s.requires.as_ref().is_some_and(|r|r==&s.id||!skills.contains(r)){return Err("Invalid skill prerequisite".into());}}
        for s in &rules.skills {let mut seen=BTreeSet::new();let mut next=Some(s.id.as_str());while let Some(id)=next {if !seen.insert(id){return Err("Cyclic skill prerequisites".into());}next=rules.skill(id)?.requires.as_deref();}}
        Ok(Some(rules))
    }
    pub fn equipment(&self,id:&str)->Result<&EquipmentDef> {self.equipment.iter().find(|e|e.id==id).ok_or_else(||"Unknown equipment".into())}
    pub fn skill(&self,id:&str)->Result<&SkillRule> {self.skills.iter().find(|s|s.id==id).ok_or_else(||"Unknown skill progression".into())}
}
pub fn job_matches(job:&str,required:&str)->bool {required=="beginner"||job==required||job.strip_suffix('2')==Some(required)}

impl World {
    pub fn player_stats(&self,p:&Player)->Bonuses {
        let mut stats=Bonuses {hp:self.combat.growth.hp(p.level),mp:self.combat.growth.mp(p.level),attack:self.combat.growth.attack(p.level),defense:0,regen:self.combat.growth.mp_regen};
        if let Some(rules)=&self.progression {
            for instance in p.progress.equipped.values() {
                if let Some(g)=p.progress.gear.get(instance) {if let Ok(d)=rules.equipment(&g.definition) {stats.add(&d.bonus,1);stats.add(&d.enhancement,g.enhancement);}}
            }
            for (id,rank) in &p.progress.skills {if let Ok(s)=rules.skill(id){if s.passive {stats.add(&s.bonus,*rank);}}}
        }
        stats
    }
    pub fn refresh_resources(&self,p:&mut Player,heal:bool) {let stats=self.player_stats(p);p.max_hp=stats.hp;p.max_mp=stats.mp;p.hp=if heal{stats.hp}else{p.hp.min(stats.hp)};p.mp=if heal{stats.mp}else{p.mp.min(stats.mp)};}
    pub fn init_progress(&self,p:&mut Player,legacy:bool)->Result<()> {
        let Some(rules)=&self.progression else{return Ok(());};
        if p.progress.initialized{return Ok(());}
        p.progress.initialized=true;p.progress.skill_points=p.level;p.progress.quick_skill="burst".into();
        if legacy {p.progress.skills.insert("burst".into(),1);p.progress.skill_points=p.level-1;}
        for id in &rules.starter_equipment {self.give_gear(p,id)?;}
        Ok(())
    }
    pub fn give_gear(&self,p:&mut Player,definition:&str)->Result<String> {
        self.progression.as_ref().ok_or("Progression unavailable")?.equipment(definition)?;
        if p.progress.gear.len()+p.progress.storage_gear.len()>=256{return Err("장비 보관 한도 256개입니다.".into());}
        let id=format!("g_{}",&random_token()?[..24]);
        if p.progress.gear.contains_key(&id)||p.progress.storage_gear.contains_key(&id){return Err("Equipment ID collision".into());}
        p.progress.gear.insert(id.clone(),Gear{definition:definition.into(),enhancement:0});Ok(id)
    }
    pub fn validate_progress(&self,p:&Player)->Result<()> {
        let Some(rules)=&self.progression else{return Ok(());};let g=&p.progress;
        if !g.initialized||!JOBS.contains(&g.job.as_str())||g.coins>1_000_000_000||g.storage_coins>1_000_000_000||g.gear.len()+g.storage_gear.len()>256
            ||g.equipped.len()>6||g.skills.len()>64||g.skill_points>p.level {return Err("Invalid player progression".into());}
        let mut spent=0u32;
        for (id,rank) in &g.skills {let rule=rules.skill(id)?;if *rank==0||*rank>rule.max_rank||p.level<rule.level||!job_matches(&g.job,&rule.job)
            ||rule.requires.as_ref().is_some_and(|r|!g.skills.contains_key(r)){return Err("Invalid learned skill".into());}spent+=rank;}
        if spent+g.skill_points!=p.level{return Err("Skill point total differs from earned levels".into());}
        let quick=rules.skill(&g.quick_skill)?;if quick.passive{return Err("Passive quickslot".into());}
        for (id,gear) in g.gear.iter().chain(g.storage_gear.iter()) {if !valid_id(id)||gear.enhancement>rules.enhancement_costs.len() as u32{return Err("Invalid equipment instance".into());}rules.equipment(&gear.definition)?;}
        if g.gear.keys().any(|id|g.storage_gear.contains_key(id)){return Err("Duplicate stored equipment instance".into());}
        let mut equipped=BTreeSet::new();
        for (slot,id) in &g.equipped {let gear=g.gear.get(id).ok_or("Equipped item missing")?;let d=rules.equipment(&gear.definition)?;
            if slot!=&d.slot||!equipped.insert(id)||p.level<d.level||!job_matches(&g.job,&d.job){return Err("Invalid equipped slot".into());}}
        if let Some(services)=&self.services {
            for (id,count) in &g.quests {let q=services.quests.iter().find(|q|q.id==*id).ok_or("Unknown active quest")?;if *count>q.count||g.completed.contains(id){return Err("Invalid quest progress".into());}}
            if g.completed.iter().any(|id|!services.quests.iter().any(|q|q.id==*id)){return Err("Unknown completed quest".into());}
        }
        if g.guild.as_ref().is_some_and(|id|!valid_id(id))||(!g.guild_name.is_empty()&&(!text_ok(&g.guild_name,16)||g.guild.as_deref()!=Some(p.id.as_str()))){return Err("Invalid guild membership".into());}
        self.inventory_ok(&g.storage)?;Ok(())
    }
    pub fn progress_command(&mut self,id:&str,action:&str,key:&str)->Result<String> {
        let rules=self.progression.as_ref().ok_or("Progression unavailable")?;
        let mut p=self.players[id].clone();if p.hp==0{return Err("쓰러진 동안 사용할 수 없습니다.".into());}
        let notice=match action {
            "equip"=>{let gear=p.progress.gear.get(key).ok_or("장비가 없습니다.")?;let d=rules.equipment(&gear.definition)?;
                if p.level<d.level||!job_matches(&p.progress.job,&d.job){return Err("레벨 또는 직업 조건이 맞지 않습니다.".into());}
                p.progress.equipped.insert(d.slot.clone(),key.into());format!("{} 장착",d.name)}
            "unequip"=>{if p.progress.equipped.remove(key).is_none(){return Err("빈 장비 슬롯입니다.".into());}"장비 해제".into()}
            "learn"=>{let s=rules.skill(key)?;let rank=*p.progress.skills.get(key).unwrap_or(&0);
                if p.progress.skill_points==0||rank>=s.max_rank||p.level<s.level||!job_matches(&p.progress.job,&s.job)
                    ||s.requires.as_ref().is_some_and(|r|!p.progress.skills.contains_key(r)){return Err("습득 조건 또는 스킬 포인트를 확인하세요.".into());}
                p.progress.skills.insert(key.into(),rank+1);p.progress.skill_points-=1;format!("스킬 {}단계 습득",rank+1)}
            "bind"=>{let s=rules.skill(key)?;if s.passive||!p.progress.skills.contains_key(key){return Err("습득한 액티브 스킬만 등록할 수 있습니다.".into());}p.progress.quick_skill=key.into();"X 스킬 등록".into()}
            "job"=>{
                let valid=if p.progress.job=="beginner" {p.level>=5&&["warrior","mage","archer","rogue"].contains(&key)}
                    else {p.level>=20&&!p.progress.job.ends_with('2')&&key==format!("{}2",p.progress.job)};
                if !valid{return Err("1차 전직은 레벨 5, 같은 계열의 2차 전직은 레벨 20부터 가능합니다.".into());}
                if p.position.map_id!=self.config.spawn.map_id{return Err("마을에서 전직하세요.".into());}
                p.progress.job=key.into();"전직을 완료했습니다.".into()}
            "enhance"=>{
                if p.position.map_id!=self.config.spawn.map_id{return Err("마을에서 강화하세요.".into());}
                let gear=p.progress.gear.get(key).ok_or("장비가 없습니다.")?;let rank=gear.enhancement as usize;
                let cost=*rules.enhancement_costs.get(rank).ok_or("최대 강화입니다.")?;
                if p.progress.coins<cost||p.inventory.get(&rules.enhancement_material).copied().unwrap_or(0)==0{return Err("강화 재화 또는 재료가 부족합니다.".into());}
                p.progress.coins-=cost;let count=p.inventory[&rules.enhancement_material];if count==1{p.inventory.remove(&rules.enhancement_material);}else{p.inventory.insert(rules.enhancement_material.clone(),count-1);}
                let roll=u32::from_str_radix(&random_token()?[..8],16)?;
                if u64::from(roll)*100<(u64::from(u32::MAX)+1)*u64::from(rules.enhancement_chances[rank]) {p.progress.gear.get_mut(key).unwrap().enhancement+=1;"강화 성공".into()}
                else {"강화 실패: 장비와 강화 단계는 보존됩니다.".into()}}
            _=>return Err("Unknown progression action".into()),
        };
        self.refresh_resources(&mut p,false);self.validate_progress(&p)?;save_player(&self.root,&p)?;self.players.insert(id.into(),p);Ok(notice)
    }
}
