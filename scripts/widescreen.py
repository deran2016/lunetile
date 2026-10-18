"""Geometry patches applied only after migrate_project validates all stock source hashes."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

RULES={
 'Game_Map':[
  ('(self.height - 15) * 128','[self.height * 128 - Graphics.height * 4, 0].max'),
  ('(self.width - 20) * 128','[self.width * 128 - Graphics.width * 4, 0].max')],
 'Game_Player':[
  ('($game_map.width - 20) * 128','[$game_map.width * 128 - Graphics.width * 4, 0].max'),
  ('($game_map.height - 15) * 128','[$game_map.height * 128 - Graphics.height * 4, 0].max'),
  ('x * 128 - CENTER_X','x * 128 - (Graphics.width / 2 - 16) * 4'),
  ('y * 128 - CENTER_Y','y * 128 - (Graphics.height / 2 - 16) * 4'),
  ('> CENTER_Y','> (Graphics.height / 2 - 16) * 4'),
  ('< CENTER_Y','< (Graphics.height / 2 - 16) * 4'),
  ('> CENTER_X','> (Graphics.width / 2 - 16) * 4'),
  ('< CENTER_X','< (Graphics.width / 2 - 16) * 4')],
 'Sprite_Timer':[('640 - self.bitmap.width','Graphics.width - self.bitmap.width')],
 'Spriteset_Map':[
  ('@viewport1 = Viewport.new(0, 0, 640, 480)','@viewport1 = Viewport.new(*Lunetile.map_rect)'),
  ('Viewport.new(0, 0, 640, 480)','Viewport.new(0, 0, Graphics.width, Graphics.height)')],
 'Spriteset_Battle':[
  ('Viewport.new(0, 0, 640, 320)','Viewport.new(0, 0, Graphics.width, Graphics.height - 160)'),
  ('Viewport.new(0, 0, 640, 480)','Viewport.new(0, 0, Graphics.width, Graphics.height)'),
  ('@battleback_sprite.src_rect.set(0, 0, 640, 320)','Lunetile.cover(@battleback_sprite, Graphics.width, Graphics.height - 160)')],
 'Game_Actor':[
  ('self.index * 160 + 80','self.index * (Graphics.width / 4) + Graphics.width / 8'),
  ('return 464','return Graphics.height - 16')],
 'Game_Enemy':[
  ('return $data_troops[@troop_id].members[@member_index].x','return ($data_troops[@troop_id].members[@member_index].x * Graphics.width / 640.0).round'),
  ('return $data_troops[@troop_id].members[@member_index].y','return ($data_troops[@troop_id].members[@member_index].y * (Graphics.height - 160) / 320.0).round')],
 'Window_Help':[('640, 64','Graphics.width, 64')],
 'Window_MenuStatus':[('480, 480','Graphics.width - 160, Graphics.height'),('i * 116','i * ((height - 32) / 4)'),('@index * 116','@index * ((height - 32) / 4)')],
 'Window_Item':[('640, 416','Graphics.width, Graphics.height - 64'),('self.height = 256','self.height = Graphics.height - 224')],
 'Window_Skill':[('640, 352','Graphics.width, Graphics.height - 128'),('self.height = 256','self.height = Graphics.height - 224')],
 'Window_SkillStatus':[('640, 64','Graphics.width, 64')],
 'Window_Target':[('336, 480','336, Graphics.height')],
 'Window_EquipRight':[('368, 192','Graphics.width - 272, 192')],
 'Window_EquipItem':[('640, 224','Graphics.width, Graphics.height - 256')],
 'Window_Status':[('640, 480','Graphics.width, Graphics.height'),('320','(Graphics.width / 2)')],
 'Window_SaveFile':[
  ('64 + file_index % 4 * 104, 640, 104','64 + file_index % 4 * ((Graphics.height - 64) / 4), Graphics.width, (Graphics.height - 64) / 4')],
 'Window_ShopCommand':[
  ('480, 64','Graphics.width - 160, 64'),('index * 160','index * ((width - 32) / 3)'),('128, 32, @commands','(width - 32) / 3 - 8, 32, @commands')],
 'Window_ShopBuy':[('368, 352','Graphics.width - 272, Graphics.height - 128')],
 'Window_ShopSell':[('640, 352','Graphics.width, Graphics.height - 128')],
 'Window_ShopNumber':[('368, 352','Graphics.width - 272, Graphics.height - 128')],
 'Window_ShopStatus':[('368, 128, 272, 352','Graphics.width - 272, 128, 272, Graphics.height - 128')],
 'Window_NameEdit':[('640, 128','Graphics.width, 128'),('320 - @max_char','Graphics.width / 2 - @max_char')],
 'Window_NameInput':[
  ('640, 352','Graphics.width, Graphics.height - 128'),('140 +','(Graphics.width - 640) / 2 + 140 +'),
  ('draw_text(428,','draw_text((Graphics.width - 640) / 2 + 428,'),('cursor_rect.set(428,','cursor_rect.set((Graphics.width - 640) / 2 + 428,')],
 'Window_Message':[
  ('super(80, 304, 480, 160)','super(0, Graphics.height - 160, Graphics.width, 160)'),
  ('self.y = 160','self.y = (Graphics.height - height) / 2'),('self.y = 304','self.y = Graphics.height - height'),
  ('self.y = 16','self.y = 0'),
  ('@gold_window.x = 560 - @gold_window.width','@gold_window.x = Graphics.width - @gold_window.width'),
  ('? 32 : 384','? 32 : Graphics.height - 96')],
 'Window_PartyCommand':[
  ('640, 64','Graphics.width, 64'),('160 + index * 160','Graphics.width / 4 + index * (Graphics.width / 4)')],
 'Window_BattleStatus':[
  ('0, 320, 640, 160','0, Graphics.height - 160, Graphics.width, 160'),('i * 160','i * (Graphics.width / 4)')],
 'Window_BattleResult':[('super(160,','super((Graphics.width - 320) / 2,'),('self.y = 160 - height / 2','self.y = (Graphics.height - 160 - height) / 2')],
 'Window_DebugLeft':[('192, 480','192, Graphics.height')],
 'Window_DebugRight':[('448, 352','Graphics.width - 192, Graphics.height - 128')],
 'Scene_Title':[
  ('@sprite.bitmap = RPG::Cache.title($data_system.title_name)','@sprite.bitmap = RPG::Cache.title($data_system.title_name)\n    Lunetile.cover(@sprite)'),
  ('320 - @command_window.width / 2','(Graphics.width - @command_window.width) / 2'),
  ('@command_window.y = 288','@command_window.y = Graphics.height * 3 / 5')],
 'Scene_Gameover':[
  ('@sprite.bitmap = RPG::Cache.gameover($data_system.gameover_name)','@sprite.bitmap = RPG::Cache.gameover($data_system.gameover_name)\n    Lunetile.cover(@sprite)')],
 'Scene_Menu':[
  ('@playtime_window.y = 224','@playtime_window.y = Graphics.height - 256'),
  ('@steps_window.y = 320','@steps_window.y = Graphics.height - 160'),
  ('@gold_window.y = 416','@gold_window.y = Graphics.height - 64')],
 'Scene_Item':[('(@item_window.index + 1) % 2 * 304','(@item_window.index + 1) % 2 * (Graphics.width - @target_window.width)')],
 'Scene_Skill':[('(@skill_window.index + 1) % 2 * 304','(@skill_window.index + 1) % 2 * (Graphics.width - @target_window.width)')],
 'Scene_End':[('320 - @command_window.width / 2','(Graphics.width - @command_window.width) / 2'),('240 - @command_window.height / 2','(Graphics.height - @command_window.height) / 2')],
 'Scene_Battle 1':[('@actor_command_window.y = 160','@actor_command_window.y = Graphics.height - 320')],
 'Scene_Battle 3':[('@actor_index * 160','@actor_index * (Graphics.width / 4)')],
 'Scene_Shop':[('@gold_window.x = 480','@gold_window.x = Graphics.width - 160'),('640, 352','Graphics.width, Graphics.height - 128')],
 'Scene_Debug':[('192, 352, 448, 128','192, Graphics.height - 128, Graphics.width - 192, 128')],
 'Scene_Load':[('RGSSXP.restore_game_compatibility','RGSSXP.restore_game_compatibility\n    $game_player.center($game_player.x, $game_player.y)')],
}

def adapt(name,text):
 changes=[]
 rules=list(RULES.get(name,[]))
 if name in ('Window_Item','Window_Skill','Window_EquipItem','Window_ShopSell'):
  rules.append(('index % 2 * (288 + 32)','index % 2 * (width / 2)'))
 for before,after in rules:
  if before not in text:raise ValueError(f'{name}: missing reviewed widescreen patch: {before}')
  if before==after:continue
  changes.append({'line':text[:text.index(before)].count('\n')+1,'before':before,'after':after,'reason':'widescreen-layout'})
  text=text.replace(before,after)
 if name=='Main':
  helper=(ROOT/'src/runtime/widescreen.rb').read_text(encoding='utf-8')+'\n'
  changes.append({'line':1,'before':'','after':helper,'reason':'widescreen-geometry-helpers'})
  text=helper+text
 return text,changes
