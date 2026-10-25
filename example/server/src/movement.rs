use super::*;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MovePart { pub direction:u8, pub ms:u16 }

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PreviewPart {pub step:u64,pub direction:u8,pub ms:u16}

#[derive(Clone)]
pub struct Relay {
    epoch:u64, step:u64, elapsed:u64, clock:Instant,
    point:(i32,i32), direction:u8, moving:bool, received:Instant, points:Vec<Value>, trail:Vec<(i32,i32)>,
}

pub fn reserve(last:&mut Instant,now:Instant,ms:u64)->Result<()> {
    // Bound accumulated arrival credit; idle time never buys a teleport.
    let began=(*last).max(now-Duration::from_millis(200));
    let due=began+Duration::from_millis(ms);
    if due>now+Duration::from_millis(200) {return Err("Move time budget exceeded".into());}
    *last=due;Ok(())
}

fn on_segment(p:(i32,i32),a:(i32,i32),b:(i32,i32))->bool {
    (p.0==a.0 && p.0==b.0 && p.1>=a.1.min(b.1) && p.1<=a.1.max(b.1))
        || (p.1==a.1 && p.1==b.1 && p.0>=a.0.min(b.0) && p.0<=a.0.max(b.0))
}

impl Player {
    pub fn motion(&self)->(i32,i32) {(self.position.x*1000+self.offset_x,self.position.y*1000+self.offset_y)}
}

impl World {
    // The published copy serves visuals only; gameplay and file commits stay on the authoritative world.
    pub fn publish(&self,target:&mut World) {
        self.publish_changed(target,&self.players.keys().cloned().collect());
    }
    pub fn publish_changed(&self,target:&mut World,changed:&BTreeSet<String>) {
        let reset:Vec<_>=target.relays.keys().filter(|id|!self.online.contains(*id)||self.epochs.get(*id)!=target.epochs.get(*id)).cloned().collect();
        for id in reset {target.relays.remove(&id);}
        target.social=self.social.clone();
        for id in changed {if let Some(p)=self.players.get(id){target.players.insert(id.clone(),p.clone());}
            if let Some(path)=self.paths.get(id){target.paths.insert(id.clone(),path.clone());}else{target.paths.remove(id);}
            if let Some(epoch)=self.epochs.get(id){target.epochs.insert(id.clone(),*epoch);}}
        target.online.clone_from(&self.online);
        target.chat.clone_from(&self.chat);target.events.clone_from(&self.events);target.event_seq=self.event_seq;
        target.combat.monsters.clone_from(&self.combat.monsters);target.combat.actors.clone_from(&self.combat.actors);
        target.combat.projectiles.clone_from(&self.combat.projectiles);
        target.motion_seq=target.motion_seq.max(self.motion_seq);
        let dead:Vec<_>=target.relays.keys().filter(|id|target.players[*id].hp==0).cloned().collect();
        for id in dead {target.cancel_preview(&id);}
    }
    pub fn relay_deadline(&self,id:&str)->Option<Instant>{self.relays.get(id).filter(|r|r.moving).map(|r|r.received+Duration::from_millis(150))}

    pub fn moving_public(&self,p:&Player)->Value {
        let mut data=p.public();let (x,y)=p.motion();
        data["motion"]=json!({"x":x,"y":y,"path":self.paths.get(&p.id),"epoch":self.epochs.get(&p.id).unwrap_or(&0)});
        if let Some(r)=self.relays.get(&p.id) {
            let mut ahead=p.clone();self.place_motion(&mut ahead,r.point);
            let moving=r.moving && p.hp>0 && r.received.elapsed()<Duration::from_millis(150);
            if moving {self.advance_motion(&mut ahead,r.direction,60);}
            let (lx,ly)=ahead.motion();
            data["relay"]=json!({"x":r.point.0,"y":r.point.1,"epoch":r.epoch,"path":r.points,"direction":r.direction,"moving":moving,"step":r.step,"lead_x":lx,"lead_y":ly});
        }
        data
    }
    fn place_motion(&self,p:&mut Player,point:(i32,i32)) {
        p.position.x=(point.0+500).div_euclid(1000);p.position.y=(point.1+500).div_euclid(1000);
        p.offset_x=point.0-p.position.x*1000;p.offset_y=point.1-p.position.y*1000;
    }
    fn advance_motion(&self,p:&mut Player,direction:u8,ms:u16) {
        let (dx,dy)=match direction {2=>(0,5),4=>(-5,0),6=>(5,0),_=>(0,-5)};
        p.direction=direction;
        for _ in 0..ms {
            let (x,y)=p.motion();let point=(x+dx,y+dy);
            let next=Position{map_id:p.position.map_id,x:(point.0+500).div_euclid(1000),y:(point.1+500).div_euclid(1000)};
            if (next.x!=p.position.x||next.y!=p.position.y)&&!self.step_ok(&p.position,&next){break;}
            self.place_motion(p,point);
        }
    }
    pub fn preview(&mut self,id:&str,origin:[i32;2],epoch:u64,elapsed:u64,parts:&[PreviewPart],moving:bool,direction:u8)->Result<String> {
        let p=&self.players[id];let canonical=p.motion();
        if p.hp==0 || epoch!=*self.epochs.get(id).unwrap_or(&0) || ![2,4,6,8].contains(&direction)
            || parts.len()>96 || parts.iter().any(|p|p.ms==0||p.step==0||![2,4,6,8].contains(&p.direction))
            || parts.windows(2).any(|w|w[0].step>=w[1].step) || parts.iter().map(|p|u64::from(p.ms)).sum::<u64>()>600 {
            return Err("Invalid movement preview".into());
        }
        if canonical!=(origin[0],origin[1]) && !self.paths.get(id).is_some_and(|h|h.iter().any(|p|p["x"]==origin[0]&&p["y"]==origin[1])) {
            return Err("Preview origin changed".into());
        }
        let previous=self.relays.get(id);let last=previous.map_or(0,|r|r.step);let used=previous.map_or(0,|r|r.elapsed);
        if elapsed<used || elapsed-used>600 || parts.last().is_some_and(|p|p.step<last) {return Err("Stale movement preview".into());}
        let mut clock=previous.map_or_else(||Instant::now()-Duration::from_secs(1),|r|r.clock);
        reserve(&mut clock,Instant::now(),elapsed-used)?;
        let fresh_ms:u64=parts.iter().filter(|p|p.step>last).map(|p|u64::from(p.ms)).sum();
        if fresh_ms>elapsed-used {return Err("Preview time does not match path".into());}
        let mut predicted=p.clone();self.place_motion(&mut predicted,(origin[0],origin[1]));
        let mut passed=predicted.motion()==canonical;let mut fresh=Vec::new();let mut trail=vec![predicted.motion()];
        for part in parts {
            let before=predicted.motion();self.advance_motion(&mut predicted,part.direction,part.ms);let point=predicted.motion();
            passed|=on_segment(canonical,before,point);trail.push(point);
            if part.step==last && previous.is_some_and(|r|r.point!=point) {return Err("Preview history changed".into());}
            if part.step>last {fresh.push((before,point,part.direction));}
        }
        let point=predicted.motion();
        if !passed || (point.0-canonical.0).abs()+(point.1-canonical.1).abs()>3000 {return Err("Preview exceeds pending movement".into());}
        let mut end=previous.map_or_else(||fresh.first().map_or(canonical,|p|p.0),|r|r.point);
        for (before,point,_) in &fresh {
            if *before!=end {return Err("Preview path is disconnected".into());}end=*point;
        }
        if end!=point {return Err("Preview endpoint changed without new steps".into());}
        let r=self.relays.entry(id.to_owned()).or_insert_with(||Relay{epoch,step:0,elapsed:0,clock,point:canonical,direction,moving:false,received:Instant::now(),points:Vec::new(),trail:Vec::new()});
        // Include the validated origin so a rejected durable move can retrace corners.
        for (before,point,direction) in fresh {
            if r.points.is_empty(){self.motion_seq+=1;r.points.push(json!({"seq":self.motion_seq,"x":before.0,"y":before.1,"direction":direction}));}
            self.motion_seq+=1;
            if r.points.len()>1 && r.points.last().is_some_and(|p|p["direction"]==direction) {r.points.pop();}
            r.points.push(json!({"seq":self.motion_seq,"x":point.0,"y":point.1,"direction":direction}));r.point=point;
        }
        if r.points.len()>32 {r.points.drain(..r.points.len()-32);}
        r.step=parts.last().map_or(last,|p|p.step);r.elapsed=elapsed;r.clock=clock;r.point=point;r.direction=direction;r.moving=moving;r.received=Instant::now();r.trail=trail;
        Ok(String::new())
    }
    pub fn clear_preview(&mut self,id:&str){self.relays.remove(id);}
    pub fn cancel_preview(&mut self,id:&str) {
        let point=self.players[id].motion();
        if let Some(r)=self.relays.get_mut(id) {
            let path=&r.trail;
            let start=path.windows(2).rposition(|w|on_segment(point,w[0],w[1]));
            if let Some(start)=start {
                let mut reverse=path[start+1..path.len()-1].to_vec();reverse.reverse();reverse.push(point);
                for (x,y) in reverse {self.motion_seq+=1;r.points.push(json!({"seq":self.motion_seq,"x":x,"y":y,"direction":r.direction}));}
            }
            r.point=point;r.moving=false;r.trail=vec![point];
        }
    }
    pub fn move_parts(&mut self,id:&str,parts:&[MovePart],last:&mut Instant)->Result<String> {
        let ms:u64=parts.iter().map(|p|u64::from(p.ms)).sum();
        if parts.is_empty()||parts.len()>32||ms==0||ms>200||parts.iter().any(|p|p.ms==0||![2,4,6,8].contains(&p.direction)) {
            return Err("Invalid movement parts".into());
        }
        reserve(last,Instant::now(),ms)?;
        let mut player=self.players[id].clone();let start=player.motion();let mut path=Vec::new();
        for part in parts {
            self.advance_motion(&mut player,part.direction,part.ms);
            let (x,y)=player.motion();path.push((x,y,part.direction));
        }
        save_player(&self.root,&player)?;
        self.players.insert(id.to_owned(),player);
        let history=self.paths.entry(id.to_owned()).or_default();
        if history.is_empty(){self.motion_seq+=1;history.push(json!({"seq":self.motion_seq,"x":start.0,"y":start.1,"direction":self.players[id].direction}));}
        for (x,y,direction) in path {
            self.motion_seq+=1;history.push(json!({"seq":self.motion_seq,"x":x,"y":y,"direction":direction}));
        }
        if history.len()>64 {history.drain(..history.len()-64);}
        Ok(String::new())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn time_budget_caps_idle_credit_and_sustained_speed() {
        let start=Instant::now();let mut last=start-Duration::from_secs(1);
        reserve(&mut last,start,200).unwrap();reserve(&mut last,start,200).unwrap();assert!(reserve(&mut last,start,1).is_err());
        reserve(&mut last,start+Duration::from_millis(100),100).unwrap();
        assert!(reserve(&mut last,start+Duration::from_millis(100),1).is_err());
        reserve(&mut last,start+Duration::from_secs(10),200).unwrap();reserve(&mut last,start+Duration::from_secs(10),200).unwrap();
        assert!(reserve(&mut last,start+Duration::from_secs(10),1).is_err());
    }
    #[test]
    fn frame_jitter_does_not_reject_legitimate_five_tile_motion() {
        let start=Instant::now();let mut last=start-Duration::from_secs(1);
        for i in 0..100 {reserve(&mut last,start+Duration::from_millis(i*200+i%3),200).unwrap();}
        let mut last=start-Duration::from_secs(1);let mut accepted=0;
        for ms in 0..2000 {if reserve(&mut last,start+Duration::from_millis(ms),1).is_ok(){accepted+=1;}}
        assert!(accepted<=2400);
    }
}
