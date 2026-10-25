"""Reviewed template-only script optimizations. General migration stays unchanged."""
import hashlib,json,re,subprocess
from pathlib import Path
from rxdata import read,write
from migrate_project import ROOT,transform as xp_transform
from migrate_vxa import transform as vxa_transform

P='Lunetile::StockScripts'

def digest(data):return hashlib.sha256(data).hexdigest()

def methods(source):
 lines=source.replace('\r\n','\n').splitlines(keepends=True);result={}
 for i,line in enumerate(lines):
  found=re.match(r'^  def (?:self\.)?([\w!?=]+)(.*)',line)
  if not found:continue
  end=next(j for j in range(i+1,len(lines)) if lines[j].rstrip()=='  end')
  result[found[1]]=''.join(lines[i:end+1]).replace('  def self.','  def ',1)
 return result

def guarded(body,key,args):
 first,rest=body.split('\n',1)
 return first+f'\n    return {P}::ORIGINALS[:{key}].bind_call(self{","+args if args else ""}) unless {P}.enabled?\n'+rest

def scalar_moves(body):
 pattern=r'(?m)^(\s*)(@real_[xy]) = \[([^,\n]+), ([^\]\n]+)\]\.(min|max)(?: if ([^\n]+))?$'
 def convert(m):
  indent,target,left,right,mode,condition=m.groups();pad=indent+('  ' if condition else '')
  text=(f'{pad}lunetile_value = {left}\n{pad}lunetile_bound = {right}\n'
        f'{pad}{target} = lunetile_value {">" if mode=="min" else "<"} lunetile_bound ? lunetile_bound : lunetile_value')
  return f'{indent}if {condition}\n{text}\n{indent}end' if condition else text
 return re.sub(pattern,convert,body)

def positions(body):
 lines=[]
 for line in body.splitlines(keepends=True):
  matches=list(re.finditer(r'@(x|y)\s*(?:[+\-*/]?=)(?!=)',line))
  if matches:
   last=matches[-1][1]
   line=line.rstrip('\n')+f'; {P}.moved(self); @{last}\n'
  lines.append(line)
 return ''.join(lines)

def script_guard(body):
 lines=[]
 for line in body.splitlines(keepends=True):
  if 'eval(' in line:
   if ';' in line:line=line.replace('eval(',P+'.disable!; eval(',1)
   else:lines.append(re.match(r'\s*',line)[0]+P+'.disable!\n')
  lines.append(line)
 return ''.join(lines)

def generate(entries,engine):
 needed=('Game_Map','Game_Character','Game_Player','Sprite_Character','Window_SaveFile','Scene_Title','Scene_Map','Interpreter','Game_Interpreter')
 sources={e.name.decode('utf-8'):methods(e.source().decode('utf-8')) for e in entries
  if any(e.name.decode('utf-8')==n or e.name.decode('utf-8').startswith(n+' ') or e.name.decode('utf-8')==n+'Base' for n in needed)}
 selected={}
 def add(entry,name,change,args=''):
  owner=entry.split(' ')[0]
  key=engine+'_'+owner+'_'+re.sub(r'\W','_',name)
  original=sources[entry][name];before=selected.get((owner,name),(key,original))[1]
  selected[owner,name]=(key,change(before,key,args))
 def guard_change(fn):return lambda body,key,args:guarded(fn(body),key,args)
 def replace_checked(body,before,after):
  if body.count(before)!=1:raise ValueError('Reviewed template method marker changed: '+before)
  return body.replace(before,after,1)
 if engine=='xp':
  def sprite(body):
   body=replace_checked(body,'@tile_id = @character.tile_id','@lunetile_bitmap = nil\n      @tile_id = @character.tile_id')
   body=replace_checked(body,'self.src_rect.set(sx, sy, @cw, @ch)',
    'if @lunetile_bitmap != bitmap || @lunetile_character != @character || @lunetile_sx != sx || @lunetile_sy != sy || @lunetile_cw != @cw || @lunetile_ch != @ch\n'
    '        self.src_rect.set(sx, sy, @cw, @ch)\n'
    '        @lunetile_bitmap, @lunetile_character = bitmap, @character\n'
    '        @lunetile_sx, @lunetile_sy, @lunetile_cw, @lunetile_ch = sx, sy, @cw, @ch\n      end')
   body=replace_checked(body,'self.x = @character.screen_x',
    'lunetile_map = $game_map\n    lunetile_rx, lunetile_dx = @character.real_x, lunetile_map.display_x\n'
    '    if @lunetile_position_character != @character || @lunetile_position_map != lunetile_map || @lunetile_rx != lunetile_rx || @lunetile_dx != lunetile_dx\n'
    '      @lunetile_screen_x = @character.screen_x\n      @lunetile_rx, @lunetile_dx = lunetile_rx, lunetile_dx\n    end\n'
    '    self.x = @lunetile_screen_x unless @x == @lunetile_screen_x')
   body=replace_checked(body,'self.y = @character.screen_y',
    'lunetile_ry, lunetile_dy = @character.real_y, lunetile_map.display_y\n    lunetile_jump = @character.jumping?\n'
    '    if @lunetile_position_character != @character || @lunetile_position_map != lunetile_map || lunetile_jump || @lunetile_jump || @lunetile_ry != lunetile_ry || @lunetile_dy != lunetile_dy\n'
    '      @lunetile_screen_y = @character.screen_y\n      @lunetile_ry, @lunetile_dy = lunetile_ry, lunetile_dy\n    end\n'
    '    @lunetile_jump = lunetile_jump\n    @lunetile_position_character, @lunetile_position_map = @character, lunetile_map\n'
    '    self.y = @lunetile_screen_y unless @y == @lunetile_screen_y')
   return display_values(body)
  add('Sprite_Character','update',guard_change(sprite))
  add('Game_Character 2','update_move',guard_change(scalar_moves))
  lookups=[('Game_Map','passable?','events.values','x,y','x,y,d,self_event'),
   ('Game_Character 1','passable?','$game_map.events.values','new_x,new_y','x,y,d'),
   ('Game_Player','check_event_trigger_here','$game_map.events.values','@x,@y','triggers'),
   ('Game_Player','check_event_trigger_there','$game_map.events.values','new_x,new_y','triggers'),
   ('Game_Player','check_event_trigger_touch','$game_map.events.values','x,y','x,y')]
  for entry,name,before,coords,args in lookups:
   owner='self' if entry=='Game_Map' else '$game_map'
   def lookup(body,key,args,before=before,coords=coords,owner=owner):
    if before not in body:raise ValueError('Reviewed event lookup missing')
    return guarded(body.replace(before,f'({P}.candidates({owner},{coords}) || {before})'),key,args)
   add(entry,name,lookup,args)
  def check_event(body,key,args):
   return ('  def check_event(x, y)\n'
    f'    events = {P}.candidates($game_map,x,y)\n'
    f'    return {P}::ORIGINALS[:{key}].bind_call(self,x,y) unless events\n'
    '    events.each { |event| return event.id if event.x == x && event.y == y }\n'
    '    $game_map.events.values\n  end\n')
  add('Game_Map','check_event',check_event,'x,y')
  position_entries=['Game_Character 1','Game_Character 2','Game_Character 3']
 else:
  def rectangle(body):
   return replace_checked(body,'self.src_rect.set(sx, sy, @cw, @ch)',
    'if @lunetile_bitmap != bitmap || @lunetile_character != @character || @lunetile_sx != sx || @lunetile_sy != sy || @lunetile_cw != @cw || @lunetile_ch != @ch\n'
    '        self.src_rect.set(sx, sy, @cw, @ch)\n'
    '        @lunetile_bitmap, @lunetile_character = bitmap, @character\n'
    '        @lunetile_sx, @lunetile_sy, @lunetile_cw, @lunetile_ch = sx, sy, @cw, @ch\n      end\n      @src_rect')
  add('Sprite_Character','update_src_rect',guard_change(rectangle))
  add('Sprite_Character','update_bitmap',guard_change(lambda b:replace_checked(b,'@tile_id = @character.tile_id','@lunetile_bitmap = nil\n      @tile_id = @character.tile_id')))
  def position(body):
   body=replace_checked(body,'move_animation(@character.screen_x - x, @character.screen_y - y)',
    'screen_x, screen_y = @character.screen_x, @character.screen_y\n    move_animation(screen_x - x, screen_y - y)')
   body=replace_checked(body,'self.x = @character.screen_x','self.x = screen_x')
   return replace_checked(body,'self.y = @character.screen_y','self.y = screen_y')
  add('Sprite_Character','update_position',guard_change(position))
  add('Sprite_Character','update_other',guard_change(lambda b:display_values(b).replace('  def update_other\n','  def update_other\n    check_live\n',1)))
  add('Game_CharacterBase','update_move',guard_change(scalar_moves))
  for name,predicate in [('events_xy','pos?'),('events_xy_nt','pos_nt?')]:
   def query(body,key,args,predicate=predicate,name=name):
    return (f'  def {name}(x, y)\n    events = {P}.candidates(self,x,y)\n'
     f'    return {P}::ORIGINALS[:{key}].bind_call(self,x,y) unless events\n'
     f'    events.select {{ |event| event.{predicate}(x,y) }}\n  end\n')
   add('Game_Map',name,query,'x,y')
  def preview(body,key,args):
   first,rest=body.split('\n',1)
   return guarded(first+'\n    @lunetile_header = DataManager.load_header(@file_index)\n    @lunetile_preview = true\n'+rest.rsplit('  end',1)[0]+'  ensure\n    @lunetile_preview = false\n    @lunetile_header = nil\n  end\n',key,args)
  add('Window_SaveFile','refresh',preview)
  for name,args in [('draw_party_characters','x,y'),('draw_playtime','x,y,width,align')]:
   add('Window_SaveFile',name,lambda b,k,a:replace_checked(b,'header = DataManager.load_header(@file_index)','header = @lunetile_preview ? @lunetile_header : DataManager.load_header(@file_index)'),args)
  position_entries=['Game_CharacterBase','Game_Character']
 # Position notifications are inserted at the write, before the next callback/query.
 for entry in position_entries:
  for name,body in sources[entry].items():
   if name=='initialize' or not re.search(r'@(x|y)\s*(?:[+\-*/]?=)(?!=)',body):continue
   args=arguments(body)
   def movement(body,key,args):
    # update_move was already guarded when its allocation-free body was generated.
    return positions(body) if 'ORIGINALS[:'+key+']' in body else guarded(positions(body),key,args)
   add(entry,name,movement,args)
 for entry,names in sources.items():
  for name,body in names.items():
   if 'eval(' in body and (entry.startswith('Interpreter') or entry in ('Game_Interpreter','Game_Character','Game_Character 2')):
    add(entry,name,lambda b,k,a:script_guard(b),arguments(body))
 def setup(body,key,args):
  first,rest=body.split('\n',1)
  return first+'\n    '+P+'.setup_begin\n'+rest.rsplit('  end',1)[0]+'  ensure\n    '+P+'.setup_end\n  end\n'
 add('Game_Map','setup',setup,'map_id')
 def reset(body,key,args):
  first,rest=body.split('\n',1)
  return first+'\n    '+P+'.invalidate\n'+rest
 add('Scene_Title','main' if engine=='xp' else 'start',reset)
 add('Scene_Map','main' if engine=='xp' else 'start',reset)
 # The helper is outside saved Game_* objects; loading a different map also changes identity.
 common=(ROOT/'src/template_scripts/stock_performance.rb').read_text(encoding='utf-8')
 blocks=[common]
 for (owner,name),(key,body) in selected.items():
  blocks.append(f"{P}.install(::{owner},:{name},:{key},<<'LUNETILE_STOCK_METHOD')\n{body}\nLUNETILE_STOCK_METHOD\n")
 return '\n'.join(blocks).encode('utf-8')

def arguments(body):
 declaration=body.splitlines()[0]
 if '(' not in declaration:return ''
 return ','.join(part.strip().split('=')[0].strip() for part in declaration.split('(',1)[1].rsplit(')',1)[0].split(','))

def display_values(body):
 for name,value in [('visible','(not @character.transparent)'),('visible','!@character.transparent'),
   ('opacity','@character.opacity'),('blend_type','@character.blend_type'),('bush_depth','@character.bush_depth')]:
  before=f'self.{name} = {value}'
  if before in body:body=body.replace(before,f'lunetile_value = {value}\n    self.{name} = lunetile_value unless @{name} == lunetile_value\n    lunetile_value',1)
 return body

def optimize(project,engine,ruby):
 project=Path(project);ext='rxdata' if engine=='xp' else 'rvdata2'
 raw_path=project/f'Data/Scripts.{ext}';raw=raw_path.read_bytes();entries=read(raw)
 original=read((ROOT/f'template-{engine}/Data/Scripts.{ext}').read_bytes())
 replacements,_=(xp_transform if engine=='xp' else vxa_transform)(original,widescreen=True,high_refresh=True)
 expected=[replacements.get(i,e.source()) for i,e in enumerate(original)]
 if len(entries)!=len(original) or any(e.name!=o.name or e.id!=o.id or e.source()!=s for e,o,s in zip(entries,original,expected)):
  raise ValueError('Unreviewed converted template script collection')
 main=next(i for i,e in enumerate(entries) if e.name==b'Main')
 tail=original[main].source().replace(b'\r\n',b'\n') if engine=='xp' else original[main].source()
 if not entries[main].source().endswith(tail):raise ValueError('Reviewed stock Main suffix changed')
 helper=generate(entries,engine)
 updated=entries[main].source()[:-len(tail)]+helper+b'\n'+tail
 result=write(entries,{main:updated});again=read(result)
 assert all(e.raw==again[i].raw for i,e in enumerate(entries) if i!=main)
 source=project/'migration/stock-performance.rb';source.write_bytes(helper)
 checked=subprocess.run([str(ruby),'--disable-gems','-c',str(source)],capture_output=True,text=True)
 if checked.returncode:raise ValueError('Template performance helper syntax failed: '+checked.stderr)
 manifest_path=project/'migration/manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
 record=dict(version=1,engine=engine,main_index=main,helper_sha256=digest(helper),scripts_sha256_before=digest(raw),scripts_sha256_after=digest(result),unchanged_entries=len(entries)-1,syntax=checked.stdout.strip())
 manifest['script_performance']=record
 manifest['result_scripts_sha256']=digest(result)
 manifest['scripts'][main]['source_sha256_after']=digest(updated)
 manifest['scripts'][main]['changes'].append({'line':1,'reason':'template-stock-script-performance-v1'})
 raw_path.write_bytes(result)
 manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return record
