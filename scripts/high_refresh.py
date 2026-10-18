"""Reviewed stock source transformations for the fixed 120 Hz timing profile."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RULES={
 'Game_Character 1':[
  ('(@jump_peak * @jump_peak - n * n) / 2','(@jump_peak * @jump_peak - n * n) / 18')],
 'Game_Character 2':[
  ('if @anime_count > 18 - @move_speed * 2','if RGSSXP::Timing.legacy_tick? && @anime_count > (18 - @move_speed * 2) * 3'),
  ('if @stop_count > (40 - @move_frequency * 2) * (6 - @move_frequency)','if RGSSXP::Timing.legacy_tick? && @stop_count > ((40 - @move_frequency * 2) * (6 - @move_frequency) + 1) * 3 - 1'),
  ('distance = 2 ** @move_speed','distance = RGSSXP::Timing.step_distance(self, :@lunetile_move_remainder, 2 ** @move_speed)'),
  ('(@real_x * @jump_count + @x * 128) / (@jump_count + 1)','(@real_x.to_f * @jump_count + @x * 128) / (@jump_count + 1)'),
  ('(@real_y * @jump_count + @y * 128) / (@jump_count + 1)','(@real_y.to_f * @jump_count + @y * 128) / (@jump_count + 1)'),
  ('def move_type_custom','def move_type_custom\n    return unless RGSSXP::Timing.legacy_tick?'),
  ('command.parameters[0] * 2 - 1','command.parameters[0] * 6 - 1')],
 'Game_Character 3':[('@jump_peak = 10 + distance - @move_speed','@jump_peak = (10 + distance - @move_speed) * 3')],
 'Game_Map':[
  ('distance = 2 ** @scroll_speed','distance = RGSSXP::Timing.step_distance(self, :@lunetile_scroll_remainder, 2 ** @scroll_speed)'),
  ('@fog_sx / 8.0','@fog_sx / 24.0'),('@fog_sy / 8.0','@fog_sy / 24.0')],
 'Game_Screen':[('(@shake_power * @shake_speed * @shake_direction) / 10.0','(@shake_power * @shake_speed * @shake_direction) / 30.0')],
 'Game_Picture':[('@rotate_speed / 2.0','@rotate_speed / 6.0')],
 'Interpreter 1':[
  ('        Graphics.update\n','        3.times { Graphics.update }\n'),
  ('def setup_starting_event','def setup_starting_event\n    return false unless RGSSXP::Timing.legacy_tick?')],
 'Interpreter 3':[('@wait_count = @parameters[0] * 2','@wait_count = @parameters[0] * 6')],
 'Game_Event':[
  ('    check_event_trigger_auto\n','    check_event_trigger_auto if RGSSXP::Timing.legacy_tick?\n'),
  ('unless @interpreter.running?','if !@interpreter.running? && RGSSXP::Timing.legacy_tick?')],
 'Game_CommonEvent':[('unless @interpreter.running?','if !@interpreter.running? && RGSSXP::Timing.legacy_tick?')],
 'Sprite_Battler':[('self.opacity += 3','self.opacity += 1'),('self.opacity -= 3','self.opacity -= 1')],
 'Window_Message':[('self.contents_opacity += 24','self.contents_opacity += 8'),('self.opacity -= 48','self.opacity -= 16'),('@input_number_window.contents_opacity += 24','@input_number_window.contents_opacity += 8')],
 'Arrow_Base':[('% 8','% 24'),('@blink_count < 4','@blink_count < 12')],
 'Scene_Battle 1':[('      update_phase4\n','      update_phase4 if RGSSXP::Timing.legacy_tick?\n')],
 'Scene_Battle 2':[('@phase5_wait_count = 100','@phase5_wait_count = 300')],
 'Scene_Battle 4':[('@wait_count = 8','@wait_count = 24')],
 'Window_SaveFile':[('@frame_count / Graphics.frame_rate','@frame_count / file.timing_rate')],
 'Scene_Load':[('    $game_party.refresh','    RGSSXP::Timing.import_save(file)\n    $game_party.refresh')],
 'Scene_Menu':[
  ('[s1, s2, s3, s4, s5, s6]','[s1, s2, s3, s4, s5, s6, "화면 설정"]'),
  ('    @command_window.index = @menu_index','    @command_window.height = [@command_window.height, Graphics.height - 256].min\n    @command_window.index = @menu_index')],
}

def adapt(name,text):
 rules=list(RULES.get(name,[]))
 if name in ('Game_Screen','Game_Picture','Game_Map'):
  import re
  for line in text.splitlines():
   if re.fullmatch(r'\s+@\w*duration = duration',line):rules.append((line,line+' * 3'))
 # An identical duration assignment can occur in two methods; apply it once globally.
 rules=list(dict.fromkeys(rules))
 changes=[]
 for before,after in rules:
  if before not in text:raise ValueError(f'{name}: missing reviewed high-refresh patch: {before}')
  changes.append({'line':text[:text.index(before)].count('\n')+1,'before':before,'after':after,'reason':'stock120-timing'})
  text=text.replace(before,after)
 if name=='Main':
  helper=(ROOT/'src/runtime/stock_timing.rb').read_text(encoding='utf-8')+'\n'
  changes.append({'line':1,'before':'','after':helper,'reason':'stock120-settings-and-save-import'})
  text=helper+text
 return text,changes
