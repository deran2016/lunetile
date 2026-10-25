use super::*;

#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Growth {
    pub max_level:u32,pub base_hp:u32,pub base_mp:u32,pub base_attack:u32,
    pub hp_per_level:u32,pub mp_per_level:u32,pub attack_per_level:u32,pub exp_per_level:u32,
    pub mp_regen:u32,
}
impl Growth {
    pub fn hp(&self,level:u32)->u32 { self.base_hp+(level-1)*self.hp_per_level }
    pub fn mp(&self,level:u32)->u32 { self.base_mp+(level-1)*self.mp_per_level }
    pub fn attack(&self,level:u32)->u32 { self.base_attack+(level-1)*self.attack_per_level }
    pub fn needed(&self,level:u32)->u32 { if level>=self.max_level {0} else {level*self.exp_per_level} }
    pub fn grant(&self,p:&mut Player,amount:u32) {
        let mut total=u64::from(p.exp)+u64::from(amount);
        while p.level<self.max_level && total>=u64::from(self.needed(p.level)) {
            total-=u64::from(self.needed(p.level));p.level+=1;
            p.max_hp=self.hp(p.level);p.max_mp=self.mp(p.level);p.hp=p.max_hp;p.mp=p.max_mp;
        }
        p.exp=if p.level==self.max_level {0} else {total as u32};
    }
}
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Skill {
    pub id:String,pub name:String,pub icon:String,pub bonus:u32,pub mp_cost:u32,pub cooldown_ms:u64,pub range:i32,
    #[serde(default)] pub motion:String,
    #[serde(default)] pub motion_ms:u32,
    #[serde(default)] pub hit_effect:String,
    #[serde(default)] pub projectile:Option<ProjectileDef>,
    #[serde(default)] pub particles:particles::Bindings,
}
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ProjectileDef {pub flight_ms:u32,pub delay_ms:u32,pub radius:i32}
#[derive(Clone)]
pub struct Projectile {
    pub id:u64,pub source:String,pub origin:Position,pub target:Position,pub cells:Vec<Position>,
    pub skill:Skill,pub power:u32,pub began:Instant,pub deadline:Instant,
}
impl Projectile {
    pub fn public(&self,now:Instant)->Value {
        let definition=self.skill.projectile.as_ref().unwrap();
        json!({"id":self.id,"source":self.source,"position":self.origin,"target":self.target,"cells":self.cells,
            "icon":self.skill.icon,"flight_ms":definition.flight_ms,"delay_ms":definition.delay_ms,"radius":definition.radius,
            "elapsed_ms":now.saturating_duration_since(self.began).as_millis() as u64})
    }
}
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MonsterDef {
    pub id:String,pub name:String,pub character:String,pub hp:u32,pub attack:u32,pub exp:u32,
    pub move_ms:u64,pub attack_ms:u64,pub respawn_ms:u64,pub aggro:i32,pub leash:i32,
    pub spawns:Vec<Position>,
}
#[derive(Clone)]
pub struct Monster {
    pub id:String,pub kind:String,pub position:Position,pub origin:Position,pub hp:u32,pub direction:u8,
    pub moved:Instant,pub attacked:Instant,pub respawn:Option<Instant>,pub damage:BTreeMap<String,u32>,
    pub returning:bool,
}
#[derive(Clone)]
pub struct Actor {pub cooldowns:BTreeMap<String,Instant>,pub combat_until:Instant,pub regen:Instant,pub respawn:Option<Instant>}
impl Actor {fn new(now:Instant)->Self {Self {cooldowns:BTreeMap::new(),combat_until:now,regen:now,respawn:None}}}
#[derive(Clone)]
pub struct Combat {
    pub growth:Growth,pub skills:BTreeMap<String,Skill>,pub definitions:BTreeMap<String,MonsterDef>,
    pub monsters:BTreeMap<String,Monster>,pub actors:BTreeMap<String,Actor>,
    // shortcut: active throws reset on server restart; persist them before adding durable world actions.
    pub projectiles:Vec<Projectile>,
    pub particles:Vec<particles::Preset>,
}
pub fn distance(a:&Position,b:&Position)->i32 {if a.map_id!=b.map_id {i32::MAX} else {(a.x-b.x).abs()+(a.y-b.y).abs()}}

impl Combat {
    pub fn load(root:&Path)->Result<Self> {
        let growth:Growth=load_json(&root.join("data/growth.json"))?;
        if !(1..=1000).contains(&growth.max_level) || growth.base_hp==0 || growth.base_mp==0 || growth.base_attack==0
            || growth.exp_per_level==0 || [growth.base_hp,growth.base_mp,growth.base_attack,growth.hp_per_level,
                growth.mp_per_level,growth.attack_per_level,growth.exp_per_level,growth.mp_regen].iter().any(|v| *v>100_000) {
            return Err("Invalid growth definition".into());
        }
        let skills:Vec<Skill>=load_json(&root.join("data/skills.json"))?;
        let defs:Vec<MonsterDef>=load_json(&root.join("data/monsters.json"))?;
        if skills.is_empty() || skills.len()>64 || defs.len()>16 {return Err("Too many combat definitions".into());}
        let mut combat=Self {growth,skills:BTreeMap::new(),definitions:BTreeMap::new(),monsters:BTreeMap::new(),actors:BTreeMap::new(),projectiles:Vec::new(),particles:particles::load(root)?};
        for mut s in skills {
            if s.motion.is_empty(){s.motion=if s.projectile.is_some(){"throw"}else if s.id=="burst"{"magic"}else{"slash"}.into();}
            if s.motion_ms==0{s.motion_ms=if s.motion=="magic"{360}else{240};}
            if s.hit_effect.is_empty(){s.hit_effect=if s.motion=="magic"{"magic"}else{"spark"}.into();}
            if !valid_id(&s.id)||!text_ok(&s.name,32)||!asset_ok(&s.icon)||s.bonus>100_000||s.mp_cost>100_000
                || !(200..=60_000).contains(&s.cooldown_ms)||!(1..=10).contains(&s.range)
                || !["slash","magic","throw"].contains(&s.motion.as_str())||!["spark","magic"].contains(&s.hit_effect.as_str())
                || !(80..=2000).contains(&s.motion_ms) {return Err("Invalid skill".into());}
            if (s.motion=="throw")!=s.projectile.is_some() {return Err("Throw motion requires projectile settings".into());}
            if let Some(p)=&s.projectile {if !(100..=2000).contains(&p.flight_ms)||p.delay_ms<p.flight_ms||p.delay_ms>10_000||!(1..=3).contains(&p.radius) {return Err("Invalid projectile settings".into());}}
            if [&s.particles.cast,&s.particles.hit,&s.particles.explosion].iter().any(|id|id.as_ref().is_some_and(|id|!combat.particles.iter().any(|p|p.id==*id))) {return Err("Unknown particle preset in skill".into());}
            if combat.skills.insert(s.id.clone(),s).is_some(){return Err("Duplicate skill ID".into());}
        }
        let now=Instant::now();
        for d in defs {
            if !valid_id(&d.id)||!text_ok(&d.name,32)||!asset_ok(&d.character)||d.hp==0||d.hp>1_000_000||d.attack>100_000||d.exp>1_000_000
                || !(100..=60_000).contains(&d.move_ms)||!(200..=60_000).contains(&d.attack_ms)
                || !(100..=600_000).contains(&d.respawn_ms)||!(1..=20).contains(&d.aggro)||d.leash<d.aggro||d.leash>40||d.spawns.len()>64 {return Err("Invalid monster".into());}
            for (i,p) in d.spawns.iter().enumerate() {
                let id=format!("{}_{i}",d.id);if !valid_id(&id){return Err("Monster spawn ID too long".into());}
                combat.monsters.insert(id.clone(),Monster {id,kind:d.id.clone(),position:p.clone(),origin:p.clone(),hp:d.hp,direction:2,
                    moved:now,attacked:now,respawn:None,damage:BTreeMap::new(),returning:false});
            }
            if combat.definitions.insert(d.id.clone(),d).is_some(){return Err("Duplicate monster ID".into());}
        }
        if combat.monsters.len()>64{return Err("At most 64 monster spawns".into());}
        Ok(combat)
    }
}
impl World {
    pub fn emit(&mut self,map:u32,recipient:Option<&str>,mut data:Value) {
        self.event_seq+=1;data["seq"]=json!(self.event_seq);
        self.events.push((map,recipient.map(str::to_owned),std::sync::Arc::new(data)));if self.events.len()>256{self.events.remove(0);}
    }
    pub fn step_ok(&self,from:&Position,to:&Position)->bool {
        if !self.position_ok(to)||from.map_id!=to.map_id{return false;}
        let (bit,reverse)=match (to.x-from.x,to.y-from.y){(0,1)=>(1,8),(-1,0)=>(2,4),(1,0)=>(4,2),(0,-1)=>(8,1),_=>return false};
        let m=&self.maps[&to.map_id];
        m.passages[from.y as usize][from.x as usize]&bit==0&&m.passages[to.y as usize][to.x as usize]&reverse==0
            &&!self.npcs.values().any(|n| distance(&n.position,to)==0)
    }
    fn line_ok(&self,a:&Position,b:&Position)->bool {
        if a.map_id!=b.map_id{return false;}
        let (nx,ny)=((b.x-a.x).abs(),(b.y-a.y).abs());let (dx,dy)=((b.x-a.x).signum(),(b.y-a.y).signum());
        let (mut ix,mut iy)=(0,0);let mut p=a.clone();
        while ix<nx||iy<ny {
            let decision=(1+2*ix)*ny-(1+2*iy)*nx;
            let q=Position {map_id:p.map_id,x:p.x+if decision<=0{dx}else{0},y:p.y+if decision>=0{dy}else{0}};
            if decision==0 {
                // Both sides of an exact grid corner must be clear.
                let x=Position{map_id:p.map_id,x:q.x,y:p.y};let y=Position{map_id:p.map_id,x:p.x,y:q.y};
                if !self.step_ok(&p,&x)||!self.step_ok(&p,&y)||!self.step_ok(&x,&q)||!self.step_ok(&y,&q){return false;}
            } else if !self.step_ok(&p,&q){return false;}
            if decision<=0{ix+=1;}
            if decision>=0{iy+=1;}p=q;
        }
        true
    }
    pub fn attack(&mut self,id:&str,direction:u8,skill:&str,now:Instant)->Result<String> {
        if !self.online.contains(id){return Err("Not connected".into());}
        if self.root.join("transactions/pending.json").exists(){return Err("Pending save recovery: restart server".into());}
        let mut skill=self.combat.skills.get(skill).ok_or("Unknown skill")?.clone();
        let mut player=self.players[id].clone();
        if player.hp==0{return Err("Player is dead".into());}
        let mut shape="fan".to_owned();
        if let Some(rules)=&self.progression {
            if skill.id!="basic" {
                let rule=rules.skill(&skill.id)?;let rank=player.progress.skills.get(&skill.id).copied().unwrap_or(0);
                if rank==0||rule.passive{return Err("습득한 액티브 스킬이 아닙니다.".into());}
                skill.bonus+=rule.damage_per_rank*(rank-1);shape=rule.shape.clone();
            } else if let Some(gear)=player.progress.equipped.get("weapon").and_then(|id|player.progress.gear.get(id)) {
                skill.icon=rules.equipment(&gear.definition)?.icon.clone();
            }
        }
        let (fx,fy)=match direction{2=>(0,1),4=>(-1,0),6=>(1,0),8=>(0,-1),_=>return Err("Invalid direction".into())};
        let actor=self.combat.actors.entry(id.to_owned()).or_insert_with(||Actor::new(now));
        if actor.cooldowns.get(&skill.id).is_some_and(|ready| *ready>now){return Err("스킬 재사용 대기 중입니다.".into());}
        if player.mp<skill.mp_cost{return Err("MP가 부족합니다.".into());}
        let power=self.player_stats(&player).attack+skill.bonus;
        let origin=player.position.clone();player.mp-=skill.mp_cost;player.direction=direction;
        let event=json!({"kind":"attack","source":id,"skill_id":skill.id,"direction":direction,"position":origin,
            "motion":skill.motion,"motion_ms":skill.motion_ms,"hit_effect":skill.hit_effect,"range":skill.range,"icon":skill.icon,"shape":shape,"particles":skill.particles.cast});
        if let Some(definition)=&skill.projectile {
            if self.combat.projectiles.len()>=64{return Err("동시에 사용할 수 있는 투척물 수를 초과했습니다.".into());}
            let mut target=origin.clone();
            for _ in 0..skill.range {let next=Position{map_id:target.map_id,x:target.x+fx,y:target.y+fy};if !self.step_ok(&target,&next){break;}target=next;}
            let mut cells=Vec::new();
            for dy in -definition.radius..=definition.radius {for dx in -definition.radius..=definition.radius {
                let cell=Position{map_id:target.map_id,x:target.x+dx,y:target.y+dy};
                if self.position_ok(&cell)&&self.line_ok(&target,&cell)&&!self.npcs.values().any(|n|distance(&n.position,&cell)==0){cells.push(cell);}
            }}
            let projectile=Projectile{id:self.event_seq+1,source:id.into(),origin:origin.clone(),target,cells,power,skill:skill.clone(),began:now,deadline:now+Duration::from_millis(u64::from(definition.delay_ms))};
            save_player(&self.root,&player)?;self.players.insert(id.into(),player);
            let mut event=event;event["projectile"]=projectile.public(now);
            self.combat.projectiles.push(projectile);self.emit(origin.map_id,None,event);
        } else {
            let targets=self.combat.monsters.values().filter(|m| {
                let dx=m.position.x-origin.x;let dy=m.position.y-origin.y;let forward=dx*fx+dy*fy;let side=(dx*fy-dy*fx).abs();
                m.hp>0&&m.position.map_id==origin.map_id&&forward>=0&&forward<=skill.range&&side<=if shape=="line"{0}else{forward}&&self.line_ok(&origin,&m.position)
            }).map(|m|m.id.clone()).collect();
            let save_cast=skill.mp_cost!=0||self.players[id].direction!=direction;
            self.commit_hits(id,power,&origin,&skill,targets,player,save_cast,event,now)?;
        }
        let actor=self.combat.actors.get_mut(id).unwrap();actor.cooldowns.insert(skill.id.clone(),now+Duration::from_millis(skill.cooldown_ms));actor.combat_until=now+Duration::from_secs(3);actor.regen=now;
        Ok(String::new())
    }
    fn commit_hits(&mut self,id:&str,power:u32,origin:&Position,skill:&Skill,targets:Vec<String>,player:Player,save_cast:bool,event:Value,now:Instant)->Result<()> {
        let mut monsters=Vec::new();let mut hits=Vec::new();let mut awards:BTreeMap<String,u32>=BTreeMap::new();
        for target in targets {
            let current=&self.combat.monsters[&target];
            let mut mob=current.clone();let damage=power.min(mob.hp);mob.hp-=damage;
            *mob.damage.entry(id.to_owned()).or_default()+=damage;
            hits.push(json!({"kind":"damage","target":mob.id,"amount":damage,"monster":true,"source":id,
                "position":mob.position,"hit_effect":skill.hit_effect,"killed":mob.hp==0,"particles":skill.particles.hit}));
            if mob.hp==0 {
                let eligible:Vec<_>=mob.damage.iter().filter(|(pid,_)| self.online.contains(*pid)&&self.players[*pid].hp>0&&self.players[*pid].position.map_id==mob.position.map_id).map(|(p,d)|(p.clone(),*d)).collect();
                let reward=self.combat.definitions[&mob.kind].exp;let total:u64=eligible.iter().map(|(_,d)|u64::from(*d)).sum();
                let mut shares:Vec<_>=eligible.into_iter().map(|(p,d)|{let weighted=u64::from(reward)*u64::from(d);(p,(weighted/total) as u32,weighted%total)}).collect();
                shares.sort_by(|a,b| b.2.cmp(&a.2).then(a.0.cmp(&b.0)));
                let remainder=reward-shares.iter().map(|s|s.1).sum::<u32>();
                for (i,(pid,amount,_)) in shares.into_iter().enumerate(){
                    let reward=amount+u32::from((i as u32)<remainder);let members=self.reward_members(&pid,&mob.position);let count=members.len() as u32;
                    for (index,member) in members.into_iter().enumerate(){*awards.entry(member).or_default()+=reward/count+u32::from((index as u32)<reward%count);}
                }
                mob.respawn=Some(now+Duration::from_millis(self.combat.definitions[&mob.kind].respawn_ms));
            }
            monsters.push(mob);
        }
        let mut updates=BTreeMap::new();updates.insert(id.to_owned(),player);
        let mut level_ups=Vec::new();
        for (pid,amount) in &awards {
            let p=updates.entry(pid.clone()).or_insert_with(||self.players[pid].clone());let old=p.level;
            self.combat.growth.grant(p,*amount);if p.progress.initialized {p.progress.skill_points+=p.level-old;}
            self.refresh_resources(p,p.level>old);if p.level>old{level_ups.push(pid.clone());}
        }
        let loot_notices=self.reward_kills(&mut updates,&monsters)?;
        let updates:Vec<_>=updates.into_values().collect();
        if monsters.iter().any(|m|m.hp==0){journal::commit(&self.root,&updates)?;}
        else if save_cast{save_player(&self.root,&updates[0])?;}
        for p in updates{self.players.insert(p.id.clone(),p);}
        for m in monsters{self.combat.monsters.insert(m.id.clone(),m);}
        self.emit(origin.map_id,None,event);
        for hit in hits{self.emit(origin.map_id,None,hit);}
        for (pid,text) in loot_notices {self.emit(origin.map_id,Some(&pid),json!({"kind":"loot","text":text}));}
        for (pid,amount) in awards {self.emit(origin.map_id,Some(&pid),json!({"kind":"experience","amount":amount}));}
        for pid in level_ups {self.emit(origin.map_id,Some(&pid),json!({"kind":"level_up","level":self.players[&pid].level}));}
        Ok(())
    }
    fn detonate_projectiles(&mut self,now:Instant)->Result<()> {
        while let Some(index)=self.combat.projectiles.iter().position(|p|now>=p.deadline) {
            let projectile=self.combat.projectiles[index].clone();
            let targets=self.combat.monsters.values().filter(|m|m.hp>0&&projectile.cells.iter().any(|p|distance(p,&m.position)==0)&&self.line_ok(&projectile.target,&m.position)).map(|m|m.id.clone()).collect();
            let event=json!({"kind":"explosion","id":projectile.id,"source":projectile.source,"position":projectile.target,"radius":projectile.skill.projectile.as_ref().unwrap().radius,"particles":projectile.skill.particles.explosion});
            let player=self.players[&projectile.source].clone();
            self.commit_hits(&projectile.source,projectile.power,&projectile.target,&projectile.skill,targets,player,false,event,now)?;
            if let Some(actor)=self.combat.actors.get_mut(&projectile.source){actor.combat_until=now+Duration::from_secs(3);actor.regen=now;}
            self.combat.projectiles.remove(index);
        }
        Ok(())
    }
    pub fn tick(&mut self,now:Instant)->Result<()> {
        self.social_tick();
        if self.root.join("transactions/pending.json").exists(){return Err("저장 복구가 필요합니다. 서버를 다시 실행하세요.".into());}
        self.detonate_projectiles(now)?;
        for id in self.online.clone() {
            let mut p=self.players[&id].clone();let regen=self.player_stats(&p).regen;
            let a=self.combat.actors.entry(id.clone()).or_insert_with(||Actor::new(now));
            if p.hp==0 {
                let ready=*a.respawn.get_or_insert(now+Duration::from_secs(2));
                if now>=ready {p.position=self.config.spawn.clone();p.offset_x=0;p.offset_y=0;p.hp=p.max_hp;p.mp=p.max_mp;
                    save_player(&self.root,&p)?;self.players.insert(id.clone(),p.clone());
                    self.paths.remove(&id);self.relays.remove(&id);*self.epochs.entry(id.clone()).or_default()+=1;
                    self.combat.actors.insert(id.clone(),Actor::new(now));
                    self.emit(p.position.map_id,None,json!({"kind":"respawn","target":id,"position":p.position}));
                }
            } else if now>=a.combat_until && now.duration_since(a.regen)>=Duration::from_secs(1) {
                a.regen=now;
                if p.mp<p.max_mp {p.mp=p.mp.saturating_add(regen).min(p.max_mp);save_player(&self.root,&p)?;self.players.insert(id,p);}
            }
        }
        for id in self.combat.monsters.keys().cloned().collect::<Vec<_>>() {
            let mut m=self.combat.monsters[&id].clone();let def=self.combat.definitions[&m.kind].clone();
            if let Some(ready)=m.respawn {if now>=ready {m.hp=def.hp;m.position=m.origin.clone();m.respawn=None;m.damage.clear();m.moved=now;m.attacked=now;m.returning=false;}self.combat.monsters.insert(id,m);continue;}
            if distance(&m.position,&m.origin)>=def.leash{m.returning=true;}
            if m.returning && distance(&m.position,&m.origin)==0{m.returning=false;m.hp=def.hp;m.damage.clear();}
            let target=self.online.iter().filter_map(|id|self.players.get(id)).filter(|p|!m.returning&&p.hp>0&&distance(&p.position,&m.position)<=def.aggro)
                .min_by_key(|p|(distance(&p.position,&m.position),p.id.clone())).cloned();
            if let Some(mut p)=target.clone() {
                if distance(&p.position,&m.position)<=1&&self.line_ok(&m.position,&p.position)&&now.duration_since(m.attacked)>=Duration::from_millis(def.attack_ms) {
                    let damage=def.attack.saturating_sub(self.player_stats(&p).defense).max(1);p.hp=p.hp.saturating_sub(damage);save_player(&self.root,&p)?;self.players.insert(p.id.clone(),p.clone());m.attacked=now;
                    let a=self.combat.actors.entry(p.id.clone()).or_insert_with(||Actor::new(now));a.combat_until=now+Duration::from_secs(3);
                    self.emit(p.position.map_id,None,json!({"kind":"damage","target":p.id,"amount":damage,"monster":false}));
                    if p.hp==0 {self.cancel_preview(&p.id);self.emit(p.position.map_id,None,json!({"kind":"death","target":p.id}));}
                }
            }
            if now.duration_since(m.moved)>=Duration::from_millis(def.move_ms) {
                let goal=target.map_or_else(||m.origin.clone(),|p|p.position);
                if distance(&m.position,&goal)>1 || distance(&goal,&m.origin)==0 {
                    let dx=(goal.x-m.position.x).signum();let dy=(goal.y-m.position.y).signum();
                    let steps=if (goal.x-m.position.x).abs()>=(goal.y-m.position.y).abs(){[(dx,0),(0,dy)]}else{[(0,dy),(dx,0)]};
                    for (dx,dy) in steps {let next=Position{map_id:m.position.map_id,x:m.position.x+dx,y:m.position.y+dy};
                        if (dx!=0||dy!=0)&&distance(&next,&m.origin)<=def.leash&&self.step_ok(&m.position,&next){m.position=next;m.direction=if dx<0{4}else if dx>0{6}else if dy<0{8}else{2};break;}}
                }
                m.moved=now;
            }
            self.combat.monsters.insert(id,m);
        }
        Ok(())
    }
}
