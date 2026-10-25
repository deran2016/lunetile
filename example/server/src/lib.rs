use serde::{de::DeserializeOwned, Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::fs::{self, File, OpenOptions};
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

pub type Result<T> = std::result::Result<T, Box<dyn std::error::Error + Send + Sync>>;
pub const MAX_REQUEST: usize = 16_384;
pub const MAX_RESPONSE: usize = 262_144;
pub const PROTOCOL: u32 = 11;
pub mod storage;
pub mod metrics;
pub mod publishing;
pub mod accounts;
pub mod combat;
pub mod particles;
pub mod progression;
pub mod services;
pub mod social;
mod journal;
mod movement;
pub use movement::{MovePart,PreviewPart};
fn one()->u32 {1}
fn fifty()->u32 {50}

#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Config {
    pub bind: String,
    pub max_clients: usize,
    pub max_accounts: usize,
    pub spawn: Position,
    pub character: String,
    pub starting_items: BTreeMap<String, u32>,
}

#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Position {
    pub map_id: u32,
    pub x: i32,
    pub y: i32,
}

#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Item {
    pub id: String,
    pub name: String,
    pub description: String,
    pub heal: u32,
    pub max_stack: u32,
    #[serde(default)] pub mp_heal:u32,
    #[serde(default)] pub icon:String,
}

#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Npc {
    pub id: String,
    pub name: String,
    pub character: String,
    pub position: Position,
    pub dialogue: String,
    pub reward: BTreeMap<String, u32>,
}

#[derive(Clone, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Map {
    pub id: u32,
    pub name: String,
    pub width: i32,
    pub height: i32,
    // Each tile has XP passage bits: down=1, left=2, right=4, up=8.
    pub passages: Vec<Vec<u8>>,
}

#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Player {
    #[serde(default)] pub progress:progression::Progress,
    pub id: String,
    pub token: String,
    pub name: String,
    pub character: String,
    pub position: Position,
    #[serde(default)] pub offset_x:i32,
    #[serde(default)] pub offset_y:i32,
    pub direction: u8,
    pub hp: u32,
    pub max_hp: u32,
    pub inventory: BTreeMap<String, u32>,
    pub claimed_npcs: BTreeSet<String>,
    #[serde(default="one")] pub schema:u32,
    #[serde(default="one")] pub level:u32,
    #[serde(default)] pub exp:u32,
    #[serde(default="fifty")] pub mp:u32,
    #[serde(default="fifty")] pub max_mp:u32,
}

impl Player {
    fn public(&self) -> Value {
        json!({"id":self.id,"name":self.name,"character":self.character,
            "position":self.position,"direction":self.direction,"hp":self.hp,"max_hp":self.max_hp,"level":self.level,
            "weapon":self.progress.equipped.get("weapon").and_then(|id|self.progress.gear.get(id)).map(|gear|&gear.definition)})
    }
}

#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case", deny_unknown_fields)]
pub enum Command {
    AccountRegister {protocol:u32,username:String,password:String},
    AccountLogin {protocol:u32,username:String,password:String},
    AccountPoll,
    CharacterCreate {slot:usize,appearance:usize,name:String},
    CharacterSelect {slot:usize},
    CharacterClaim {id:String,token:String},
    Register { protocol: u32, name: String },
    Login { protocol: u32, id: String, token: String },
    Poll,
    Social {action:String,key:String,amount:u32,text:String,revision:u64},
    Service {action:String,key:String,amount:u32},
    Progress { action:String, key:String },
    Move { seq: u64, origin:[i32;2], epoch:u64, parts: Vec<MovePart> },
    Preview {origin:[i32;2],epoch:u64,elapsed:u64,parts:Vec<PreviewPart>,moving:bool,direction:u8},
    Talk { npc_id: String },
    Use { item_id: String },
    Chat { text: String },
    Attack { skill_id:String, direction:u8 },
}

#[derive(Clone, Default, Serialize)]
pub struct MoveAck {
    pub seq: u64,
    pub accepted: bool,
}

impl MoveAck {
    pub fn process(&mut self, world: &mut World, id: &str, command: Command, last_move: &mut Instant, last_chat: &mut Instant) -> Result<String> {
        let movement = if let Command::Move { seq, .. } = &command {
            if self.seq.checked_add(1) != Some(*seq) { return Err("Invalid movement sequence".into()); }
            Some(*seq)
        } else { None };
        let result = world.command(id, command, last_move, last_chat);
        if let Some(seq) = movement { self.seq = seq; self.accepted = result.is_ok();if result.is_err(){world.cancel_preview(id);} }
        result
    }

    pub fn state(&self, world: &World, id: &str, notice: &str) -> Value {
        let mut state = world.state(id, notice);
        state["move_ack"] = json!(self);
        state
    }
}

pub fn load_json<T: DeserializeOwned>(path: &Path) -> Result<T> {
    if fs::metadata(path)?.len() > 8 * 1024 * 1024 {
        return Err(format!("{} exceeds 8 MiB", path.display()).into());
    }
    let bytes = fs::read(path)?;
    let bytes = bytes.strip_prefix(b"\xef\xbb\xbf").unwrap_or(&bytes);
    serde_json::from_slice(bytes).map_err(|e| format!("{}: {e}", path.display()).into())
}

pub fn valid_id(id: &str) -> bool {
    !id.is_empty() && id.len() <= 48 && id.bytes().all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
}

fn text_ok(text: &str, max: usize) -> bool {
    !text.trim().is_empty() && text.chars().count() <= max && !text.chars().any(char::is_control)
}

// Windows replace keeps the old file in place until the fully flushed temporary is ready.
#[cfg(windows)]
fn replace_file(source: &Path, target: &Path) -> io::Result<()> {
    use std::os::windows::ffi::OsStrExt;
    #[link(name = "kernel32")]
    extern "system" { fn MoveFileExW(from: *const u16, to: *const u16, flags: u32) -> i32; }
    let source: Vec<u16> = source.as_os_str().encode_wide().chain(Some(0)).collect();
    let target: Vec<u16> = target.as_os_str().encode_wide().chain(Some(0)).collect();
    if unsafe { MoveFileExW(source.as_ptr(), target.as_ptr(), 1 | 8) } == 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

#[cfg(not(windows))]
fn replace_file(source: &Path, target: &Path) -> io::Result<()> { fs::rename(source, target) }

pub fn save_player(root: &Path, player: &Player) -> Result<()> {
    if !valid_id(&player.id) { return Err("Invalid player file ID".into()); }
    if storage::stage(root,std::slice::from_ref(player)){return Ok(());}
    save_player_now(root,player)
}
fn save_player_now(root: &Path, player: &Player) -> Result<()> {
    let target = root.join("players").join(format!("{}.json", player.id));
    let temporary = target.with_extension("json.tmp");
    let bytes = serde_json::to_vec_pretty(player)?;
    let mut file = File::create(&temporary)?;
    file.write_all(&bytes)?;
    file.write_all(b"\n")?;
    file.sync_all()?;
    drop(file);
    if target.exists() {
        let backup = target.with_extension("json.bak");
        let link=target.with_extension("json.bak.tmp");
        if link.exists(){fs::remove_file(&link)?;}
        // The previous atomic commit already synced these bytes; a link avoids copying and syncing them again.
        if fs::hard_link(&target,&link).is_err(){fs::copy(&target,&link)?;OpenOptions::new().write(true).open(&link)?.sync_all()?;}
        replace_file(&link,&backup)?;
    }
    replace_file(&temporary, &target)?;
    Ok(())
}

#[cfg(windows)]
fn random_token() -> Result<String> {
    #[link(name = "bcrypt")]
    extern "system" { fn BCryptGenRandom(provider: *mut std::ffi::c_void, buffer: *mut u8, length: u32, flags: u32) -> i32; }
    let mut bytes = [0u8; 32];
    if unsafe { BCryptGenRandom(std::ptr::null_mut(), bytes.as_mut_ptr(), 32, 2) } < 0 {
        return Err("Windows secure random failed".into());
    }
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

#[cfg(not(windows))]
fn random_token() -> Result<String> { Err("This example targets Windows".into()) }

pub fn lock_directory(root: &Path) -> Result<File> {
    let mut options = OpenOptions::new();
    options.read(true).write(true).create(true).truncate(false);
    #[cfg(windows)]
    { use std::os::windows::fs::OpenOptionsExt; options.share_mode(0); }
    Ok(options.open(root.join("server.lock"))?)
}

#[derive(Clone)]
pub struct World {
    pub root: PathBuf,
    pub config: Config,
    pub items: BTreeMap<String, Item>,
    pub npcs: BTreeMap<String, Npc>,
    pub maps: BTreeMap<u32, Map>,
    pub players: BTreeMap<String, Player>,
    pub online: BTreeSet<String>,
    chat: Vec<Value>,
    pub combat:combat::Combat,
    pub progression:Option<progression::Rules>,
    pub services:Option<services::Services>,
    pub social:social::Social,
    events:Vec<(u32,Option<String>,std::sync::Arc<Value>)>,
    event_seq:u64,
    paths:BTreeMap<String,Vec<Value>>,
    motion_seq:u64,
    epochs:BTreeMap<String,u64>,
    relays:BTreeMap<String,movement::Relay>,
}

impl World {
    pub fn load(root: &Path) -> Result<Self> {
        let config: Config = load_json(&root.join("data/server.json"))?;
        let items: Vec<Item> = load_json(&root.join("data/items.json"))?;
        let npcs: Vec<Npc> = load_json(&root.join("data/npcs.json"))?;
        let maps: Vec<Map> = load_json(&root.join("data/maps.json"))?;
        let mut world = Self { root: root.to_path_buf(), config, items: BTreeMap::new(),
            npcs: BTreeMap::new(), maps: BTreeMap::new(), players: BTreeMap::new(), online: BTreeSet::new(), chat: Vec::new(),
            combat:combat::Combat::load(root)?,progression:progression::Rules::load(root)?,services:services::Services::load(root)?,social:social::Social::default(),events:Vec::new(),event_seq:0,paths:BTreeMap::new(),motion_seq:0,epochs:BTreeMap::new(),relays:BTreeMap::new() };
        if !(1..=64).contains(&world.config.max_clients) || !(1..=10_000).contains(&world.config.max_accounts) {
            return Err("max_clients must be 1..64; max_accounts must be 1..10000".into());
        }
        for item in items {
            if !valid_id(&item.id) || !text_ok(&item.name, 32) || !text_ok(&item.description, 200)
                || item.heal > 100_000 || item.mp_heal>100_000 || (!item.icon.is_empty()&&!asset_ok(&item.icon)) || !(1..=9999).contains(&item.max_stack) {
                return Err("Invalid item definition".into());
            }
            if world.items.insert(item.id.clone(), item).is_some() { return Err("Duplicate item ID".into()); }
        }
        if world.items.len() > 64 { return Err("Example supports at most 64 item types".into()); }
        for map in maps {
            if map.id == 0 || map.width < 1 || map.height < 1 || map.width > 500 || map.height > 500
                || !text_ok(&map.name, 64) || map.passages.len() != map.height as usize
                || map.passages.iter().any(|row| row.len() != map.width as usize || row.iter().any(|p| *p > 15)) {
                return Err("Invalid map dimensions or passage rows".into());
            }
            if world.maps.insert(map.id, map).is_some() { return Err("Duplicate map ID".into()); }
        }
        if !world.position_ok(&world.config.spawn) || !asset_ok(&world.config.character) {
            return Err("Invalid spawn or character asset".into());
        }
        world.inventory_ok(&world.config.starting_items)?;
        for npc in npcs {
            if !valid_id(&npc.id) || !text_ok(&npc.name, 32) || !text_ok(&npc.dialogue, 200)
                || !asset_ok(&npc.character) || !world.position_ok(&npc.position) {
                return Err("Invalid NPC definition".into());
            }
            world.inventory_ok(&npc.reward)?;
            if world.npcs.insert(npc.id.clone(), npc).is_some() { return Err("Duplicate NPC ID".into()); }
        }
        if world.npcs.len() > 64 { return Err("Example supports at most 64 NPCs".into()); }
        for m in world.combat.monsters.values(){if !world.position_ok(&m.origin)||world.npcs.values().any(|n|combat::distance(&n.position,&m.origin)==0){return Err("Invalid monster spawn".into());}}
        world.validate_services()?;
        fs::create_dir_all(root.join("players"))?;
        journal::recover(root)?;
        storage::recover(root)?;
        let mut migrations=Vec::new();
        for entry in fs::read_dir(root.join("players"))? {
            let entry = entry?;
            if entry.path().extension().and_then(|s| s.to_str()) != Some("json") { continue; }
            if !entry.file_type()?.is_file() { return Err("Player JSON must be a regular file".into()); }
            let mut player: Player = load_json(&entry.path())?;
            if !(1..=world.combat.growth.max_level).contains(&player.level){return Err("Invalid player level".into());}
            if player.hp>player.max_hp || player.mp>player.max_mp {return Err("Invalid player resource values".into());}
            if player.schema==3&&world.progression.is_none(){return Err("Schema 3 accounts require progression.json".into());}
            let legacy=player.schema==1;
            let mut needs_save=legacy;
            let migrating=world.progression.is_some() && player.schema<3;
            if migrating {world.init_progress(&mut player,true)?;needs_save=true;}
            world.validate_progress(&player)?;
            if (1..=world.combat.growth.max_level).contains(&player.level) {
                let stats=world.player_stats(&player);let hp=stats.hp;let mp=stats.mp;
                needs_save|=player.max_hp!=hp||player.max_mp!=mp;
                player.max_hp=hp;player.hp=player.hp.min(hp);player.max_mp=mp;
                player.mp=if legacy {mp} else {player.mp.min(mp)};
            }
            if entry.path().file_stem().and_then(|s| s.to_str()) != Some(&player.id)
                || !valid_id(&player.id) || player.token.len() != 64 || !player.token.bytes().all(|b| b.is_ascii_hexdigit())
                || !text_ok(&player.name, 16) || !asset_ok(&player.character) || !world.position_ok(&player.position)
                || !(-500..500).contains(&player.offset_x) || !(-500..500).contains(&player.offset_y)
                || !(1..=world.combat.growth.max_level).contains(&player.level) || !(1..=3).contains(&player.schema)
                || player.max_hp != world.player_stats(&player).hp || player.hp > player.max_hp
                || player.max_mp!=world.player_stats(&player).mp||player.mp>player.max_mp
                || (player.level<world.combat.growth.max_level && player.exp>=world.combat.growth.needed(player.level))
                || (player.level==world.combat.growth.max_level && player.exp!=0) || ![2,4,6,8].contains(&player.direction)
                || player.claimed_npcs.iter().any(|id| !world.npcs.contains_key(id)) {
                return Err(format!("Invalid player file: {}", entry.path().display()).into());
            }
            world.inventory_ok(&player.inventory)?;
            world.validate_progress(&player)?;
            if world.players.values().any(|p| p.name == player.name) { return Err("Duplicate player name".into()); }
            if needs_save {player.schema=if world.progression.is_some(){3}else{2};migrations.push((entry.path(),player.clone(),legacy,migrating));}
            world.players.insert(player.id.clone(), player);
        }
        if world.players.len() > world.config.max_accounts { return Err("Player files exceed max_accounts".into()); }
        let mut gear_ids=BTreeSet::new();
        for p in world.players.values() {
            if p.progress.gear.keys().chain(p.progress.storage_gear.keys()).any(|id|!gear_ids.insert(id)){return Err("Duplicate equipment ID across accounts".into());}
            if let Some(leader)=&p.progress.guild {let owner=world.players.get(leader).ok_or("Missing guild leader")?;
                if owner.progress.guild.as_ref()!=Some(leader)||!text_ok(&owner.progress.guild_name,16){return Err("Invalid guild ownership".into());}}
        }
        for (path,player,legacy,migrating) in migrations {
            if migrating {let backup=path.with_extension("json.pre-v7.bak");if !backup.exists(){let mut f=OpenOptions::new().create_new(true).write(true).open(&backup)?;f.write_all(&fs::read(&path)?)?;f.sync_all()?;}}
            let backup=path.with_extension("json.v1.bak");
            if legacy&&!backup.exists(){let bytes=fs::read(&path)?;let mut f=OpenOptions::new().create_new(true).write(true).open(&backup)?;f.write_all(&bytes)?;f.sync_all()?;}
            save_player(root,&player)?;
        }
        Ok(world)
    }

    fn position_ok(&self, p: &Position) -> bool {
        self.maps.get(&p.map_id).is_some_and(|m| p.x >= 0 && p.y >= 0 && p.x < m.width && p.y < m.height
            && m.passages[p.y as usize][p.x as usize] != 15)
    }

    fn inventory_ok(&self, inventory: &BTreeMap<String, u32>) -> Result<()> {
        for (id, count) in inventory {
            let item = self.items.get(id).ok_or_else(|| format!("Unknown inventory item: {id}"))?;
            if *count == 0 || *count > item.max_stack { return Err(format!("Invalid stack for {id}").into()); }
        }
        Ok(())
    }

    pub fn login(&mut self, command: Command) -> Result<(String, String)> {
        let (id, token) = match command {
            Command::Register { protocol: PROTOCOL, name } => {
                if !text_ok(&name, 16) || name != name.trim() { return Err("Name must be 1..16 characters without control characters or outer spaces".into()); }
                if self.players.len() >= self.config.max_accounts { return Err("Registration limit reached".into()); }
                if self.players.values().any(|p| accounts::name_key(&p.name)==accounts::name_key(&name)) { return Err(accounts::NAME_TAKEN.into()); }
                let token = random_token()?;
                let id = format!("p_{}", &token[..24]);
                if self.players.contains_key(&id) { return Err("Account ID collision; retry".into()); }
                let mut player = Player { progress:progression::Progress::default(), id: id.clone(), token: token.clone(), name, character: self.config.character.clone(),
                    position: self.config.spawn.clone(), offset_x:0,offset_y:0,direction: 2, hp: 70.min(self.combat.growth.hp(1)), max_hp: self.combat.growth.hp(1),
                    schema:2,level:1,exp:0,mp:self.combat.growth.mp(1),max_mp:self.combat.growth.mp(1),
                    inventory: self.config.starting_items.clone(), claimed_npcs: BTreeSet::new() };
                self.init_progress(&mut player,false)?;
                if self.progression.is_some(){player.schema=3;}
                self.validate_progress(&player)?;
                save_player(&self.root, &player)?;
                self.players.insert(id.clone(), player);
                (id, token)
            }
            Command::Login { protocol: PROTOCOL, id, token } => {
                let player = self.players.get(&id).ok_or("Invalid account or token")?;
                if player.token != token { return Err("Invalid account or token".into()); }
                (id, token)
            }
            _ => return Err("서버와 클라이언트를 함께 업데이트하세요. Protocol 11 required".into()),
        };
        if !self.online.insert(id.clone()) { return Err("Account is already connected".into()); }
        Ok((id, token))
    }

    pub fn provision(&mut self,c:&accounts::Character)->Result<()> {
        if !valid_id(&c.id)||c.token.len()!=64||!c.token.bytes().all(|b|b.is_ascii_hexdigit())||!text_ok(&c.name,16)||!asset_ok(&c.character){return Err("Invalid character reservation".into());}
        if let Some(p)=self.players.get(&c.id){return if p.token==c.token{Ok(())}else{Err("Character ownership mismatch".into())};}
        if self.players.len()>=self.config.max_accounts{return Err("Character limit reached".into());}
        if self.players.values().any(|p|accounts::name_key(&p.name)==accounts::name_key(&c.name)){return Err(accounts::NAME_TAKEN.into());}
        let mut p=Player{progress:progression::Progress::default(),id:c.id.clone(),token:c.token.clone(),name:c.name.clone(),character:c.character.clone(),position:self.config.spawn.clone(),offset_x:0,offset_y:0,direction:2,hp:70.min(self.combat.growth.hp(1)),max_hp:self.combat.growth.hp(1),schema:2,level:1,exp:0,mp:self.combat.growth.mp(1),max_mp:self.combat.growth.mp(1),inventory:self.config.starting_items.clone(),claimed_npcs:BTreeSet::new()};
        self.init_progress(&mut p,false)?;if self.progression.is_some(){p.schema=3;}self.validate_progress(&p)?;
        save_player(&self.root,&p)?;self.players.insert(p.id.clone(),p);Ok(())
    }

    pub fn state(&self, id: &str, notice: &str) -> Value {
        let player = &self.players[id];
        let now=Instant::now();let mut me=self.moving_public(player);
        me["exp"]=json!(player.exp);me["exp_next"]=json!(self.combat.growth.needed(player.level));me["mp"]=json!(player.mp);me["max_mp"]=json!(player.max_mp);
        me["attack"]=json!(self.player_stats(player).attack);
        me["defense"]=json!(self.player_stats(player).defense);
        let cooldowns:BTreeMap<_,_>=self.combat.actors.get(id).map(|a|a.cooldowns.iter().map(|(s,t)|(s,t.saturating_duration_since(now).as_millis() as u64)).collect()).unwrap_or_default();
        let map = &self.maps[&player.position.map_id];
        let left = (player.position.x-3).max(0); let top = (player.position.y-3).max(0);
        let passages:Vec<_> = map.passages[top as usize..(player.position.y+4).min(map.height) as usize].iter()
            .map(|row| &row[left as usize..(player.position.x+4).min(map.width) as usize]).collect();
        json!({"type":"state", "self":me, "progress":player.progress,"progression":self.progression,"services":self.services,"social":self.social_state(id), "inventory":player.inventory,"cooldowns":cooldowns,"particle_presets":self.combat.particles,
            "players":self.online.iter().filter_map(|id| self.players.get(id)).filter(|p| p.position.map_id == player.position.map_id).map(|p|self.moving_public(p)).collect::<Vec<_>>(),
            "npcs":self.npcs.values().filter(|n| n.position.map_id == player.position.map_id).collect::<Vec<_>>(),
            "items":self.items.values().collect::<Vec<_>>(), "chat":self.chat, "notice":notice,
            "map":{"id":player.position.map_id,"name":self.maps[&player.position.map_id].name},
            "navigation":{"map_id":player.position.map_id,"x":left,"y":top,"passages":passages},
            "projectiles":self.combat.projectiles.iter().filter(|p|p.target.map_id==player.position.map_id).map(|p|p.public(now)).collect::<Vec<_>>(),"skills":self.combat.skills.values().collect::<Vec<_>>(),"event_seq":self.event_seq,
            "events":self.events.iter().filter(|(map,recipient,_)|*map==player.position.map_id&&recipient.as_ref().is_none_or(|p|p==id)).map(|(_,_,v)|v).collect::<Vec<_>>(),
            "monsters":self.combat.monsters.values().filter(|m|m.position.map_id==player.position.map_id&&m.hp>0).map(|m|json!({"id":m.id,"name":self.combat.definitions[&m.kind].name,"character":self.combat.definitions[&m.kind].character,"position":m.position,"direction":m.direction,"hp":m.hp,"max_hp":self.combat.definitions[&m.kind].hp})).collect::<Vec<_>>()})
    }

    pub fn command(&mut self, id: &str, command: Command, last_move: &mut Instant, last_chat: &mut Instant) -> Result<String> {
        if !self.online.contains(id) { return Err("Not connected".into()); }
        if self.root.join("transactions/pending.json").exists(){return Err("Pending save recovery: restart server".into());}
        if let Command::Poll = command { return Ok(String::new()); }
        if let Command::Social{action,key,amount,text,revision}=command {if action.len()>24||key.len()>48||text.len()>128{return Err("Invalid social request".into());}return self.social_command(id,&action,&key,amount,&text,revision);}
        if let Command::Service{action,key,amount}=command {if action.len()>24||key.len()>48{return Err("Invalid service request".into());}return self.service_command(id,&action,&key,amount);}
        if let Command::Progress{action,key}=command {if action.len()>24||key.len()>48{return Err("Invalid progression request".into());}return self.progress_command(id,&action,&key);}
        if let Command::Attack {direction,skill_id}=command {return self.attack(id,direction,&skill_id,Instant::now());}
        if let Command::Move {parts,origin,epoch,..}=&command {
            if self.players[id].hp==0 {return Err("Cannot move while dead".into());}
            if self.players[id].motion()!=(origin[0],origin[1]) || *epoch!=*self.epochs.get(id).unwrap_or(&0) {return Err("Movement origin changed".into());}
            return self.move_parts(id,parts,last_move);
        }
        if let Command::Preview {origin,epoch,elapsed,parts,moving,direction}=&command {return self.preview(id,*origin,*epoch,*elapsed,parts,*moving,*direction);}
        let mut player = self.players[id].clone();
        if player.hp==0{return Err("쓰러졌습니다. 잠시 후 마을로 돌아갑니다.".into());}
        let mut dialogue=false;
        let notice = match command {
            Command::Talk { npc_id } => {
                dialogue=true;
                let npc = self.npcs.get(&npc_id).ok_or("Unknown NPC")?;
                if npc.position.map_id != player.position.map_id || (npc.position.x-player.position.x).abs()+(npc.position.y-player.position.y).abs() > 1 {
                    return Err("Move next to the NPC first".into());
                }
                let mut message = format!("{}: {}", npc.name, npc.dialogue);
                if !player.claimed_npcs.contains(&npc_id) && !npc.reward.is_empty() {
                    for (item, count) in &npc.reward {
                        let total = player.inventory.get(item).unwrap_or(&0).checked_add(*count).ok_or("Inventory overflow")?;
                        if total > self.items[item].max_stack { return Err("Inventory stack is full; reward was not claimed".into()); }
                        player.inventory.insert(item.clone(), total);
                    }
                    player.claimed_npcs.insert(npc_id);
                    message.push_str(" [첫 대화 보상 지급]");
                }
                message
            }
            Command::Use { item_id } => {
                let item = self.items.get(&item_id).ok_or("Unknown item")?;
                let count = *player.inventory.get(&item_id).ok_or("Item not owned")?;
                if (item.heal==0||player.hp==player.max_hp)&&(item.mp_heal==0||player.mp==player.max_mp) { return Err("Item cannot be used now".into()); }
                player.hp = player.hp.saturating_add(item.heal).min(player.max_hp);
                player.mp=player.mp.saturating_add(item.mp_heal).min(player.max_mp);
                if count == 1 { player.inventory.remove(&item_id); } else { player.inventory.insert(item_id, count-1); }
                format!("{} 사용: HP {}/{} · MP {}/{}", item.name, player.hp, player.max_hp,player.mp,player.max_mp)
            }
            Command::Chat { text } => {
                if !text_ok(&text, 100) || last_chat.elapsed() < Duration::from_secs(1) { return Err("Chat is limited to 100 characters and once per second".into()); }
                *last_chat = Instant::now();
                self.event_seq+=1;
                self.chat.push(json!({"seq":self.event_seq,"name":player.name,"text":text}));
                if self.chat.len() > 8 { self.chat.remove(0); }
                return Ok(String::new());
            }
            _ => return Err("Already logged in".into()),
        };
        // Commit memory only after disk succeeds: failed saves never acknowledge a reward/use.
        save_player(&self.root, &player)?;
        self.players.insert(id.to_owned(), player);
        if dialogue {self.emit(self.players[id].position.map_id,Some(id),json!({"kind":"dialogue","text":notice}));}
        Ok(notice)
    }
}

fn asset_ok(name: &str) -> bool {
    !name.is_empty() && name.len() <= 64 && name.bytes().all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
}

pub fn read_frame(reader: &mut impl Read) -> Result<Command> {
    let mut size = [0u8; 4];
    reader.read_exact(&mut size)?;
    let size = u32::from_be_bytes(size) as usize;
    if size == 0 || size > MAX_REQUEST { return Err("Invalid frame size".into()); }
    let mut bytes = vec![0; size];
    reader.read_exact(&mut bytes)?;
    Ok(serde_json::from_slice(&bytes)?)
}

pub fn write_frame(writer: &mut impl Write, value: &Value) -> Result<()> {
    let bytes = serde_json::to_vec(value)?;
    if bytes.len() > MAX_RESPONSE { return Err("Response exceeds protocol limit".into()); }
    writer.write_all(&(bytes.len() as u32).to_be_bytes())?;
    writer.write_all(&bytes)?;
    Ok(())
}
