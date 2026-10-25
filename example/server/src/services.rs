use super::*;
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Quest {pub id:String,pub name:String,pub description:String,pub level:u32,pub prerequisite:Option<String>,pub monster:String,pub count:u32,pub coins:u32,pub exp:u32,pub items:BTreeMap<String,u32>}
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Portal {pub id:String,pub name:String,pub from:Position,pub to:Position,pub level:u32}
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Loot {pub monster:String,pub coins:u32,pub material_chance:u32,pub gear_chance:u32,pub gear:Vec<String>}
#[derive(Clone,Serialize,Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Services {pub quests:Vec<Quest>,pub portals:Vec<Portal>,pub shop:BTreeMap<String,u32>,pub loot:Vec<Loot>}
pub fn take(items:&mut BTreeMap<String,u32>,id:&str,count:u32)->Result<()> {
    let owned=items.get(id).copied().unwrap_or(0);if count==0||owned<count{return Err("수량이 부족합니다.".into());}
    if owned==count{items.remove(id);}else{items.insert(id.into(),owned-count);}Ok(())
}
pub fn debit(coins:&mut u32,amount:u32)->Result<()> {if *coins<amount{return Err("재화가 부족합니다.".into());}*coins-=amount;Ok(())}
pub fn credit(coins:&mut u32,amount:u32)->Result<()> {*coins=coins.checked_add(amount).filter(|n|*n<=1_000_000_000).ok_or("재화 보유 한도입니다.")?;Ok(())}
pub fn roll()->Result<u32> {Ok(u32::from_str_radix(&random_token()?[..8],16)?)}
pub fn chance(percent:u32)->Result<bool> {Ok(u64::from(roll()?)*100<(u64::from(u32::MAX)+1)*u64::from(percent))}
impl Services {
    pub fn load(root:&Path)->Result<Option<Self>> {let path=root.join("data/services.json");if path.exists(){Ok(Some(load_json(&path)?))}else{Ok(None)}}
}
impl World {
    pub fn validate_services(&self)->Result<()> {
        let Some(s)=&self.services else{return Ok(());};let rules=self.progression.as_ref().ok_or("Services require progression")?;
        if s.quests.len()>100||s.portals.len()>100||s.shop.len()>64||s.loot.len()>64{return Err("Too many service definitions".into());}
        let mut ids=BTreeSet::new();
        for q in &s.quests {if !valid_id(&q.id)||!ids.insert(&q.id)||!text_ok(&q.name,32)||!text_ok(&q.description,200)||q.level==0||q.level>self.combat.growth.max_level||q.count==0||q.count>1000||q.coins>1_000_000||q.exp>1_000_000||!self.combat.definitions.contains_key(&q.monster){return Err("Invalid quest".into());}self.inventory_ok(&q.items)?;}
        for q in &s.quests {let mut seen=BTreeSet::new();let mut next=Some(q.id.as_str());while let Some(id)=next {if !seen.insert(id){return Err("Cyclic quests".into());}next=s.quests.iter().find(|q|q.id==id).ok_or("Missing quest prerequisite")?.prerequisite.as_deref();}}
        ids.clear();
        for p in &s.portals {if !valid_id(&p.id)||!ids.insert(&p.id)||!text_ok(&p.name,32)||!self.position_ok(&p.from)||!self.position_ok(&p.to)||p.level==0||p.level>self.combat.growth.max_level
            ||self.npcs.values().any(|n|combat::distance(&n.position,&p.to)==0){return Err("Invalid portal".into());}}
        for (id,price) in &s.shop {if !self.items.contains_key(id)||*price==0||*price>1_000_000{return Err("Invalid shop item".into());}}
        ids.clear();for l in &s.loot {if !self.combat.definitions.contains_key(&l.monster)||!ids.insert(&l.monster)||l.coins>1_000_000||l.material_chance>100||l.gear_chance>100||l.gear.len()>128{return Err("Invalid loot".into());}for id in &l.gear{rules.equipment(id)?;}}
        if !self.items.contains_key(&rules.enhancement_material){return Err("Missing enhancement material".into());}
        for rule in &rules.skills {let skill=self.combat.skills.get(&rule.id).ok_or("Missing combat skill definition")?;
            if (rule.shape=="throw")!=skill.projectile.is_some(){return Err("Skill shape and projectile settings differ".into());}}
        Ok(())
    }
    pub fn give_item(&self,items:&mut BTreeMap<String,u32>,id:&str,count:u32)->Result<()> {
        let definition=self.items.get(id).ok_or("Unknown item")?;let total=items.get(id).copied().unwrap_or(0).checked_add(count).ok_or("Item overflow")?;
        if count==0||total>definition.max_stack{return Err("아이템 수량 한도입니다.".into());}items.insert(id.into(),total);Ok(())
    }
    pub fn service_command(&mut self,id:&str,action:&str,key:&str,amount:u32)->Result<String> {
        if amount==0||amount>1_000_000{return Err("Invalid service quantity".into());}
        let definitions=self.services.as_ref().ok_or("Services unavailable")?;let mut p=self.players[id].clone();
        if p.hp==0{return Err("쓰러진 동안 사용할 수 없습니다.".into());}
        if action=="portal" {
            let portal=definitions.portals.iter().find(|v|v.id==key).ok_or("Unknown portal")?;
            if combat::distance(&p.position,&portal.from)>1||p.level<portal.level{return Err("포털 가까이 이동하고 입장 레벨을 확인하세요.".into());}
            p.position=portal.to.clone();p.offset_x=0;p.offset_y=0;save_player(&self.root,&p)?;self.players.insert(id.into(),p.clone());
            self.paths.remove(id);self.relays.remove(id);*self.epochs.entry(id.into()).or_default()+=1;
            self.emit(p.position.map_id,Some(id),json!({"kind":"respawn","target":id,"position":p.position}));return Ok("지역 이동".into());
        }
        if p.position.map_id!=self.config.spawn.map_id{return Err("마을에서 이용하세요.".into());}
        let notice=match action {
            "quest_accept"=>{let q=definitions.quests.iter().find(|q|q.id==key).ok_or("Unknown quest")?;
                if p.level<q.level||p.progress.completed.contains(key)||p.progress.quests.contains_key(key)||q.prerequisite.as_ref().is_some_and(|r|!p.progress.completed.contains(r)){return Err("퀘스트 수락 조건이 맞지 않습니다.".into());}
                p.progress.quests.insert(key.into(),0);format!("{} 수락",q.name)}
            "quest_claim"=>{let q=definitions.quests.iter().find(|q|q.id==key).ok_or("Unknown quest")?;
                if p.progress.quests.get(key).copied().unwrap_or(0)<q.count||p.progress.completed.contains(key){return Err("퀘스트가 완료되지 않았습니다.".into());}
                credit(&mut p.progress.coins,q.coins)?;for (item,count) in &q.items {self.give_item(&mut p.inventory,item,*count)?;}
                let old=p.level;self.combat.growth.grant(&mut p,q.exp);p.progress.skill_points+=p.level-old;let leveled=p.level>old;self.refresh_resources(&mut p,leveled);
                p.progress.quests.remove(key);p.progress.completed.insert(key.into());format!("{} 보상 수령",q.name)}
            "buy"=>{let price=*definitions.shop.get(key).ok_or("판매하지 않는 아이템입니다.")?;debit(&mut p.progress.coins,price.checked_mul(amount).ok_or("Price overflow")?)?;self.give_item(&mut p.inventory,key,amount)?;"구입 완료".into()}
            "sell"=>{let price=*definitions.shop.get(key).ok_or("매입하지 않는 아이템입니다.")?;take(&mut p.inventory,key,amount)?;credit(&mut p.progress.coins,(price/2).max(1).checked_mul(amount).ok_or("Price overflow")?)?;"판매 완료".into()}
            "buy_gear"=>{if amount!=1{return Err("장비는 한 번에 하나씩 구입합니다.".into());}let d=self.progression.as_ref().unwrap().equipment(key)?;debit(&mut p.progress.coins,d.price)?;self.give_gear(&mut p,key)?;"장비 구입".into()}
            "sell_gear"=>{if p.progress.equipped.values().any(|v|v==key){return Err("먼저 장비를 해제하세요.".into());}let g=p.progress.gear.remove(key).ok_or("장비가 없습니다.")?;let d=self.progression.as_ref().unwrap().equipment(&g.definition)?;credit(&mut p.progress.coins,(d.price/2).max(1))?;"장비 판매".into()}
            "store_item"=>{take(&mut p.inventory,key,amount)?;self.give_item(&mut p.progress.storage,key,amount)?;"아이템 보관".into()}
            "withdraw_item"=>{take(&mut p.progress.storage,key,amount)?;self.give_item(&mut p.inventory,key,amount)?;"아이템 꺼내기".into()}
            "store_gear"=>{if p.progress.equipped.values().any(|v|v==key){return Err("먼저 장비를 해제하세요.".into());}let g=p.progress.gear.remove(key).ok_or("장비가 없습니다.")?;p.progress.storage_gear.insert(key.into(),g);"장비 보관".into()}
            "withdraw_gear"=>{let g=p.progress.storage_gear.remove(key).ok_or("창고에 장비가 없습니다.")?;p.progress.gear.insert(key.into(),g);"장비 꺼내기".into()}
            "store_coins"=>{debit(&mut p.progress.coins,amount)?;credit(&mut p.progress.storage_coins,amount)?;"재화 보관".into()}
            "withdraw_coins"=>{debit(&mut p.progress.storage_coins,amount)?;credit(&mut p.progress.coins,amount)?;"재화 꺼내기".into()}
            _=>return Err("Unknown service action".into()),
        };
        self.validate_progress(&p)?;save_player(&self.root,&p)?;self.players.insert(id.into(),p);Ok(notice)
    }
    pub fn reward_kills(&self,updates:&mut BTreeMap<String,Player>,monsters:&[combat::Monster])->Result<Vec<(String,String)>> {
        let Some(definitions)=&self.services else{return Ok(vec![]);};let mut notices=Vec::new();
        for monster in monsters.iter().filter(|m|m.hp==0) {
            let mut eligible:Vec<_>=monster.damage.iter().filter(|(id,_)|self.online.contains(*id)&&self.players[*id].hp>0&&self.players[*id].position.map_id==monster.position.map_id).collect();
            eligible.sort_by(|a,b|b.1.cmp(a.1).then(a.0.cmp(b.0)));
            let credited:BTreeSet<_>=eligible.iter().flat_map(|(id,_)|self.reward_members(id,&monster.position)).collect();
            for id in credited {let p=updates.entry(id.clone()).or_insert_with(||self.players[&id].clone());
                for q in &definitions.quests {if q.monster==monster.kind {if let Some(count)=p.progress.quests.get_mut(&q.id){*count=(*count+1).min(q.count);}}}}
            if let (Some((id,_)),Some(loot))=(eligible.first(),definitions.loot.iter().find(|l|l.monster==monster.kind)) {
                let p=updates.get_mut(*id).unwrap();let coins=loot.coins.min(1_000_000_000-p.progress.coins);p.progress.coins+=coins;let mut text=vec![format!("재화 +{coins}")];
                if chance(loot.material_chance)? {let item=&self.progression.as_ref().unwrap().enhancement_material;let count=p.inventory.get(item).copied().unwrap_or(0);if count<self.items[item].max_stack {self.give_item(&mut p.inventory,item,1)?;text.push(format!("{} +1",self.items[item].name));}else{text.push("재료 수량 한도로 획득하지 못했습니다".into());}}
                if !loot.gear.is_empty()&&chance(loot.gear_chance)? {if p.progress.gear.len()+p.progress.storage_gear.len()<256 {let gear=&loot.gear[roll()? as usize%loot.gear.len()];self.give_gear(p,gear)?;text.push(self.progression.as_ref().unwrap().equipment(gear)?.name.clone());}else{text.push("장비 보관 한도로 획득하지 못했습니다".into());}}
                notices.push(((*id).clone(),text.join(" · ")));
            }
        }
        Ok(notices)
    }
}
