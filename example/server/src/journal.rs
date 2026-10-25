use super::*;

pub fn recover(root: &Path) -> Result<()> {
    let path=root.join("transactions/pending.json");
    if !path.exists() { return Ok(()); }
    let players: Vec<Player>=load_json(&path)?;
    if players.is_empty() || players.len()>64 || players.iter().any(|p| !valid_id(&p.id) || !(2..=3).contains(&p.schema)
        || p.token.len()!=64 || !p.token.bytes().all(|b| b.is_ascii_hexdigit()) || p.level==0
        || p.hp>p.max_hp || p.mp>p.max_mp) { return Err("Invalid pending player transaction".into()); }
    for player in players {
        let target=root.join("players").join(format!("{}.json",player.id));
        let expected=serde_json::to_value(&player)?;
        if target.exists() && load_json::<Value>(&target)?==expected { continue; }
        save_player(root,&player)?;
    }
    fs::remove_file(path)?;
    Ok(())
}

pub fn commit(root: &Path, players: &[Player]) -> Result<()> {
    if storage::stage(root,players){return Ok(());}
    let folder=root.join("transactions");fs::create_dir_all(&folder)?;
    let path=folder.join("pending.json");
    if path.exists() { return Err("Pending transaction: restart server to recover".into()); }
    let temporary=folder.join("pending.tmp");
    let mut file=File::create(&temporary)?;
    file.write_all(&serde_json::to_vec_pretty(players)?)?;file.sync_all()?;drop(file);
    replace_file(&temporary,&path)?;
    recover(root)
}
