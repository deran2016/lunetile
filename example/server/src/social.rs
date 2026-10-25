use super::*;
#[derive(Clone,Default,Serialize)]
pub struct Offer {pub coins:u32,pub items:BTreeMap<String,u32>,pub gear:BTreeSet<String>}
#[derive(Clone,Serialize)]
pub struct Trade {pub members:[String;2],pub offers:BTreeMap<String,Offer>,pub revision:u64,pub confirmed:BTreeSet<String>,#[serde(skip)]pub expires:Instant}
#[derive(Clone,Default)]
pub struct Social {pub parties:BTreeMap<String,Vec<String>>,pub invitations:BTreeMap<String,(String,String,Instant)>,pub trades:BTreeMap<String,Trade>}
impl World {
    fn nearby(&self,a:&str,b:&str)->bool {a!=b&&self.online.contains(a)&&self.online.contains(b)&&self.players[a].hp>0&&self.players[b].hp>0&&combat::distance(&self.players[a].position,&self.players[b].position)<=3}
    fn party_of(&self,id:&str)->Option<String> {self.social.parties.iter().find(|(_,members)|members.iter().any(|m|m==id)).map(|(leader,_)|leader.clone())}
    fn trade_of(&self,id:&str)->Option<String> {self.social.trades.iter().find(|(_,t)|t.members.iter().any(|m|m==id)).map(|(key,_)|key.clone())}
    pub fn social_tick(&mut self) {
        let now=Instant::now();self.social.invitations.retain(|recipient,(sender,_,expires)|*expires>now&&self.online.contains(recipient)&&self.online.contains(sender));
        self.social.trades.retain(|_,t|t.expires>now&&t.members.iter().all(|id|self.online.contains(id)&&self.players[id].hp>0)
            &&combat::distance(&self.players[&t.members[0]].position,&self.players[&t.members[1]].position)<=3);
        let mut parties=BTreeMap::new();for (_,members) in std::mem::take(&mut self.social.parties) {let members:Vec<_>=members.into_iter().filter(|id|self.online.contains(id)).collect();if let Some(leader)=members.first(){parties.insert(leader.clone(),members);}}
        self.social.parties=parties;
    }
    pub fn reward_members(&self,id:&str,position:&Position)->Vec<String> {
        let Some(leader)=self.party_of(id) else{return vec![id.into()];};
        let mut members:Vec<_>=self.social.parties[&leader].iter().filter(|pid|self.online.contains(*pid)&&self.players[*pid].hp>0&&combat::distance(&self.players[*pid].position,position)<=8).cloned().collect();
        if !members.iter().any(|p|p==id){members.push(id.into());}members.sort();members
    }
    pub fn social_state(&self,id:&str)->Value {
        let p=&self.players[id];let party=self.party_of(id).and_then(|leader|self.social.parties.get(&leader).map(|members|json!({"leader":leader,"members":members})));
        let guild=p.progress.guild.as_ref().map(|leader|json!({"leader":leader,"name":self.players.get(leader).map(|p|&p.progress.guild_name),"members":self.players.values().filter(|p|p.progress.guild.as_ref()==Some(leader)).map(|p|json!({"id":p.id,"name":p.name,"level":p.level,"online":self.online.contains(&p.id)})).collect::<Vec<_>>()}));
        let trade=self.trade_of(id).map(|key| {
            let t=&self.social.trades[&key];let mut data=json!(t);let mut gear=BTreeMap::new();
            for (owner,offer) in &t.offers {for key in &offer.gear {if let Some(item)=self.players[owner].progress.gear.get(key){gear.insert(key.clone(),item.clone());}}}
            data["gear_details"]=json!(gear);data["remaining_seconds"]=json!(t.expires.saturating_duration_since(Instant::now()).as_secs());data
        });
        json!({"party":party,"guild":guild,"invite":self.social.invitations.get(id).filter(|(_,_,deadline)|*deadline>Instant::now()).map(|(sender,kind,_)|json!({"sender":sender,"kind":kind})),
            "trade":trade,
            "online":self.online.iter().map(|id|{let p=&self.players[id];json!({"id":id,"name":p.name,"level":p.level,"hp":p.hp,"max_hp":p.max_hp,"map_id":p.position.map_id,"job":p.progress.job})}).collect::<Vec<_>>()})
    }
    fn commit_players(&mut self,players:Vec<Player>)->Result<()> {
        for p in &players{self.validate_progress(p)?;self.inventory_ok(&p.inventory)?;}
        journal::commit(&self.root,&players)?;for p in players{self.players.insert(p.id.clone(),p);}Ok(())
    }
    pub fn social_command(&mut self,id:&str,action:&str,key:&str,amount:u32,text:&str,revision:u64)->Result<String> {
        self.social_tick();if self.players[id].hp==0{return Err("쓰러진 동안 사용할 수 없습니다.".into());}
        match action {
            "party_create"=>{if self.party_of(id).is_some(){return Err("이미 파티에 가입했습니다.".into());}self.social.parties.insert(id.into(),vec![id.into()]);}
            "party_leave"=>{let leader=self.party_of(id).ok_or("파티가 없습니다.")?;let members=self.social.parties.get_mut(&leader).unwrap();members.retain(|m|m!=id);self.social_tick();}
            "party_kick"=>{let members=self.social.parties.get_mut(id).ok_or("파티장만 추방할 수 있습니다.")?;if key==id||!members.iter().any(|m|m==key){return Err("Invalid party member".into());}members.retain(|m|m!=key);}
            "guild_create"=>{let mut p=self.players[id].clone();if p.progress.guild.is_some()||!text_ok(text,16)||text.trim()!=text||self.players.values().any(|p|p.progress.guild_name==text){return Err("길드 이름 또는 가입 상태를 확인하세요.".into());}
                services::debit(&mut p.progress.coins,500)?;p.progress.guild=Some(id.into());p.progress.guild_name=text.into();self.commit_players(vec![p])?;}
            "guild_leave"=>{let mut p=self.players[id].clone();let leader=p.progress.guild.clone().ok_or("길드가 없습니다.")?;
                if leader==id{return Err("길드장은 길드 해산을 이용하세요.".into());}p.progress.guild=None;self.commit_players(vec![p])?;}
            "guild_disband"=>{if self.players[id].progress.guild.as_deref()!=Some(id){return Err("길드장만 해산할 수 있습니다.".into());}
                let players=self.players.values().filter(|p|p.progress.guild.as_deref()==Some(id)).cloned().map(|mut p|{p.progress.guild=None;p.progress.guild_name.clear();p}).collect();self.commit_players(players)?;}
            "guild_kick"=>{if id==key||self.players[id].progress.guild.as_deref()!=Some(id){return Err("길드장만 추방할 수 있습니다.".into());}let mut p=self.players.get(key).ok_or("Unknown player")?.clone();if p.progress.guild.as_deref()!=Some(id){return Err("다른 길드입니다.".into());}p.progress.guild=None;self.commit_players(vec![p])?;}
            "party_invite"|"guild_invite"|"trade_invite"=>{
                if !self.nearby(id,key){return Err("접속 중인 상대 가까이 이동하세요.".into());}
                if action=="party_invite" {if self.social.parties.get(id).is_none_or(|p|p.len()>=4)||self.party_of(key).is_some(){return Err("파티장·정원·상대 가입 상태를 확인하세요.".into());}}
                if action=="guild_invite" {if self.players[id].progress.guild.as_deref()!=Some(id)||self.players[key].progress.guild.is_some()||self.players.values().filter(|p|p.progress.guild.as_deref()==Some(id)).count()>=20{return Err("길드장·정원·상대 가입 상태를 확인하세요.".into());}}
                if action=="trade_invite"&&(self.trade_of(id).is_some()||self.trade_of(key).is_some()){return Err("이미 거래 중입니다.".into());}
                if self.social.invitations.contains_key(key){return Err("상대가 다른 초대를 확인 중입니다.".into());}
                self.social.invitations.insert(key.into(),(id.into(),action.into(),Instant::now()+Duration::from_secs(30)));
            }
            "decline"=>{self.social.invitations.remove(id);}
            "accept"=>{
                let (sender,kind,_)=self.social.invitations.get(id).ok_or("초대가 만료됐습니다.")?.clone();if !self.nearby(id,&sender){return Err("초대한 상대 가까이 이동하세요.".into());}
                if kind=="party_invite" {if self.party_of(id).is_some(){return Err("이미 파티에 가입했습니다.".into());}let members=self.social.parties.get_mut(&sender).ok_or("파티가 사라졌습니다.")?;if members.len()>=4{return Err("파티 정원입니다.".into());}members.push(id.into());}
                else if kind=="guild_invite" {if self.players[id].progress.guild.is_some()||self.players[&sender].progress.guild.as_deref()!=Some(sender.as_str())||self.players.values().filter(|p|p.progress.guild.as_deref()==Some(sender.as_str())).count()>=20{return Err("길드 가입 조건이 변경됐습니다.".into());}let mut p=self.players[id].clone();p.progress.guild=Some(sender);self.commit_players(vec![p])?;}
                else {if self.trade_of(id).is_some()||self.trade_of(&sender).is_some(){return Err("이미 거래 중입니다.".into());}
                    let members=[sender.clone(),id.into()];let offers=members.iter().map(|m|(m.clone(),Offer::default())).collect();self.social.trades.insert(sender,Trade{members,offers,revision:1,confirmed:BTreeSet::new(),expires:Instant::now()+Duration::from_secs(120)});}
                self.social.invitations.remove(id);
            }
            "trade_cancel"=>{if let Some(key)=self.trade_of(id){self.social.trades.remove(&key);}}
            "trade_item"|"trade_gear"|"trade_coins"=>{
                let trade_key=self.trade_of(id).ok_or("거래 중이 아닙니다.")?;let p=&self.players[id];let trade=self.social.trades.get_mut(&trade_key).unwrap();let offer=trade.offers.get_mut(id).unwrap();
                if action=="trade_coins" {if amount>p.progress.coins{return Err("재화가 부족합니다.".into());}offer.coins=amount;}
                else if action=="trade_item" {if amount>p.inventory.get(key).copied().unwrap_or(0){return Err("아이템이 부족합니다.".into());}if amount==0{offer.items.remove(key);}else{offer.items.insert(key.into(),amount);}}
                else {if !p.progress.gear.contains_key(key)||p.progress.equipped.values().any(|v|v==key){return Err("가방의 장비만 거래할 수 있습니다.".into());}if !offer.gear.remove(key){offer.gear.insert(key.into());}}
                trade.revision+=1;trade.confirmed.clear();
            }
            "trade_confirm"=>{
                let trade_key=self.trade_of(id).ok_or("거래 중이 아닙니다.")?;let mut trade=self.social.trades[&trade_key].clone();
                if revision!=trade.revision{return Err("거래 내용이 변경됐습니다. 다시 확인하세요.".into());}trade.confirmed.insert(id.into());
                if trade.confirmed.len()<2 {self.social.trades.insert(trade_key,trade);return Ok("상대의 거래 확인을 기다립니다.".into());}
                let mut players=[self.players[&trade.members[0]].clone(),self.players[&trade.members[1]].clone()];
                let mut transferred=[Vec::new(),Vec::new()];
                for i in 0..2 {let offer=&trade.offers[&trade.members[i]];let p=&mut players[i];services::debit(&mut p.progress.coins,offer.coins)?;
                    for (item,count) in &offer.items {services::take(&mut p.inventory,item,*count)?;}
                    for gear in &offer.gear {if p.progress.equipped.values().any(|g|g==gear){return Err("제시한 장비가 장착됐습니다.".into());}transferred[i].push((gear.clone(),p.progress.gear.remove(gear).ok_or("제시한 장비가 없습니다.")?));}}
                for i in 0..2 {let offer=&trade.offers[&trade.members[1-i]];let p=&mut players[i];services::credit(&mut p.progress.coins,offer.coins)?;
                    for (item,count) in &offer.items {self.give_item(&mut p.inventory,item,*count)?;}
                    for (key,gear) in &transferred[1-i] {if p.progress.gear.contains_key(key)||p.progress.storage_gear.contains_key(key){return Err("Equipment instance collision".into());}p.progress.gear.insert(key.clone(),gear.clone());}}
                self.commit_players(players.into())?;self.social.trades.remove(&trade_key);return Ok("거래 완료".into());
            }
            _=>return Err("Unknown social action".into()),
        }
        Ok("요청을 처리했습니다.".into())
    }
}
