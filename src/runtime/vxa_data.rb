# RGSS3 data model, isolated from RGSS1 classes before project data is loaded.
Object.send(:remove_const, :RPG)
module RPG
  class BaseItem; end
  class UsableItem < BaseItem; end
  class EquipItem < BaseItem; end
  class Actor < BaseItem; end
  class Class < BaseItem; end
  class Skill < UsableItem; end
  class Item < UsableItem; end
  class Weapon < EquipItem; end
  class Armor < EquipItem; end
  class Enemy < BaseItem; end
  class State < BaseItem; end
  class AudioFile
    attr_accessor :name, :volume, :pitch
    def initialize(name = '', volume = 100, pitch = 100)
      @name, @volume, @pitch = name, volume, pitch
    end
  end
  class BGM < AudioFile; end
  class BGS < AudioFile; end
  class ME < AudioFile; end
  class SE < AudioFile; end
end
RPG::Actor = ::Class.new unless defined?(RPG::Actor)
RPG::Actor.class_eval { attr_accessor :name, :face_index, :character_index, :initial_level, :face_name, :class_id, :character_name, :id, :features, :note, :equips, :nickname, :description, :max_level, :icon_index }
RPG::Animation = ::Class.new unless defined?(RPG::Animation)
RPG::Animation.class_eval { attr_accessor :animation2_hue, :position, :name, :animation2_name, :frames, :animation1_hue, :frame_max, :animation1_name, :timings, :id }
RPG::Animation::Frame = ::Class.new unless defined?(RPG::Animation::Frame)
RPG::Animation::Frame.class_eval { attr_accessor :cell_data, :cell_max }
RPG::Animation::Timing = ::Class.new unless defined?(RPG::Animation::Timing)
RPG::Animation::Timing.class_eval { attr_accessor :flash_duration, :se, :flash_color, :frame, :flash_scope, :condition }
RPG::Armor = ::Class.new unless defined?(RPG::Armor)
RPG::Armor.class_eval { attr_accessor :description, :name, :icon_index, :price, :note, :id, :features, :params, :etype_id, :atype_id }
RPG::BGM = ::Class.new unless defined?(RPG::BGM)
RPG::BGM.class_eval { attr_accessor :name, :volume, :pitch }
RPG::BGS = ::Class.new unless defined?(RPG::BGS)
RPG::BGS.class_eval { attr_accessor :name, :volume, :pitch }
RPG::BaseItem::Feature = ::Class.new unless defined?(RPG::BaseItem::Feature)
RPG::BaseItem::Feature.class_eval { attr_accessor :code, :data_id, :value }
RPG::Class = ::Class.new unless defined?(RPG::Class)
RPG::Class.class_eval { attr_accessor :name, :learnings, :id, :features, :note, :params, :exp_params, :icon_index, :description }
RPG::Class::Learning = ::Class.new unless defined?(RPG::Class::Learning)
RPG::Class::Learning.class_eval { attr_accessor :level, :skill_id, :note }
RPG::CommonEvent = ::Class.new unless defined?(RPG::CommonEvent)
RPG::CommonEvent.class_eval { attr_accessor :trigger, :name, :switch_id, :list, :id }
RPG::Enemy = ::Class.new unless defined?(RPG::Enemy)
RPG::Enemy.class_eval { attr_accessor :name, :gold, :battler_hue, :exp, :hit, :battler_name, :actions, :note, :id, :eva, :features, :params, :drop_items }
RPG::Enemy::Action = ::Class.new unless defined?(RPG::Enemy::Action)
RPG::Enemy::Action.class_eval { attr_accessor :condition_type, :rating, :skill_id, :condition_param2, :condition_param1 }
RPG::Enemy::DropItem = ::Class.new unless defined?(RPG::Enemy::DropItem)
RPG::Enemy::DropItem.class_eval { attr_accessor :denominator, :kind, :data_id }
RPG::Event = ::Class.new unless defined?(RPG::Event)
RPG::Event.class_eval { attr_accessor :id, :name, :x, :y, :pages }
RPG::Event::Page = ::Class.new unless defined?(RPG::Event::Page)
RPG::Event::Page.class_eval { attr_accessor :condition, :graphic, :move_type, :move_speed, :move_frequency, :move_route, :walk_anime, :step_anime, :direction_fix, :through, :priority_type, :trigger, :list }
RPG::Event::Page::Condition = ::Class.new unless defined?(RPG::Event::Page::Condition)
RPG::Event::Page::Condition.class_eval { attr_accessor :switch1_valid, :switch2_valid, :variable_valid, :self_switch_valid, :item_valid, :actor_valid, :switch1_id, :switch2_id, :variable_id, :variable_value, :self_switch_ch, :item_id, :actor_id }
RPG::Event::Page::Graphic = ::Class.new unless defined?(RPG::Event::Page::Graphic)
RPG::Event::Page::Graphic.class_eval { attr_accessor :tile_id, :character_name, :character_index, :direction, :pattern }
RPG::EventCommand = ::Class.new unless defined?(RPG::EventCommand)
RPG::EventCommand.class_eval { attr_accessor :indent, :code, :parameters }
RPG::Item = ::Class.new unless defined?(RPG::Item)
RPG::Item.class_eval { attr_accessor :description, :name, :consumable, :occasion, :icon_index, :price, :scope, :animation_id, :note, :speed, :id, :features, :effects, :damage, :success_rate, :hit_type, :itype_id, :repeats, :tp_gain }
RPG::ME = ::Class.new unless defined?(RPG::ME)
RPG::ME.class_eval { attr_accessor :name, :pitch, :volume }
RPG::Map = ::Class.new unless defined?(RPG::Map)
RPG::Map.class_eval { attr_accessor :parallax_name, :height, :events, :parallax_sx, :bgm, :tileset_id, :encounter_step, :width, :data, :bgs, :parallax_loop_y, :autoplay_bgm, :encounter_list, :autoplay_bgs, :parallax_show, :scroll_type, :parallax_loop_x, :disable_dashing, :parallax_sy, :display_name, :specify_battleback, :note, :battleback1_name, :battleback2_name }
RPG::Map::Encounter = ::Class.new unless defined?(RPG::Map::Encounter)
RPG::Map::Encounter.class_eval { attr_accessor :troop_id, :weight, :region_set }
RPG::MapInfo = ::Class.new unless defined?(RPG::MapInfo)
RPG::MapInfo.class_eval { attr_accessor :scroll_x, :name, :expanded, :order, :scroll_y, :parent_id }
RPG::MoveCommand = ::Class.new unless defined?(RPG::MoveCommand)
RPG::MoveCommand.class_eval { attr_accessor :code, :parameters }
RPG::MoveRoute = ::Class.new unless defined?(RPG::MoveRoute)
RPG::MoveRoute.class_eval { attr_accessor :repeat, :skippable, :wait, :list }
RPG::SE = ::Class.new unless defined?(RPG::SE)
RPG::SE.class_eval { attr_accessor :name, :pitch, :volume }
RPG::Skill = ::Class.new unless defined?(RPG::Skill)
RPG::Skill.class_eval { attr_accessor :message2, :description, :name, :occasion, :icon_index, :message1, :scope, :animation_id, :note, :mp_cost, :speed, :id, :features, :effects, :damage, :success_rate, :hit_type, :stype_id, :tp_cost, :required_wtype_id1, :required_wtype_id2, :repeats, :tp_gain }
RPG::State = ::Class.new unless defined?(RPG::State)
RPG::State.class_eval { attr_accessor :message2, :name, :priority, :icon_index, :message1, :message4, :restriction, :release_by_damage, :message3, :note, :id, :features, :auto_removal_timing, :min_turns, :max_turns, :chance_by_damage, :steps_to_remove, :remove_by_walking, :remove_at_battle_end, :remove_by_damage, :remove_by_restriction, :description }
RPG::System = ::Class.new unless defined?(RPG::System)
RPG::System.class_eval { attr_accessor :elements, :start_y, :airship, :test_battlers, :_, :edit_map_id, :battle_end_me, :party_members, :start_x, :ship, :battler_hue, :sounds, :variables, :battle_bgm, :version_id, :start_map_id, :battler_name, :magic_number, :switches, :gameover_me, :game_title, :title_bgm, :terms, :test_troop_id, :boat, :skill_types, :weapon_types, :armor_types, :currency_unit, :window_tone, :japanese, :opt_draw_title, :opt_use_midi, :opt_transparent, :opt_followers, :opt_slip_death, :opt_extra_exp, :opt_display_tp, :battleback1_name, :battleback2_name, :title1_name, :title2_name, :opt_floor_death }
RPG::System::Terms = ::Class.new unless defined?(RPG::System::Terms)
RPG::System::Terms.class_eval { attr_accessor :params, :etypes, :commands, :basic }
RPG::System::TestBattler = ::Class.new unless defined?(RPG::System::TestBattler)
RPG::System::TestBattler.class_eval { attr_accessor :actor_id, :level, :equips }
RPG::System::Vehicle = ::Class.new unless defined?(RPG::System::Vehicle)
RPG::System::Vehicle.class_eval { attr_accessor :start_y, :bgm, :start_x, :character_index, :character_name, :start_map_id }
RPG::Tileset = ::Class.new unless defined?(RPG::Tileset)
RPG::Tileset.class_eval { attr_accessor :id, :name, :mode, :tileset_names, :flags, :note }
RPG::Troop = ::Class.new unless defined?(RPG::Troop)
RPG::Troop.class_eval { attr_accessor :members, :name, :pages, :id }
RPG::Troop::Member = ::Class.new unless defined?(RPG::Troop::Member)
RPG::Troop::Member.class_eval { attr_accessor :y, :hidden, :x, :enemy_id }
RPG::Troop::Page = ::Class.new unless defined?(RPG::Troop::Page)
RPG::Troop::Page.class_eval { attr_accessor :list, :span, :condition }
RPG::Troop::Page::Condition = ::Class.new unless defined?(RPG::Troop::Page::Condition)
RPG::Troop::Page::Condition.class_eval { attr_accessor :turn_valid, :actor_hp, :turn_a, :turn_ending, :enemy_hp, :switch_valid, :enemy_index, :actor_valid, :actor_id, :enemy_valid, :switch_id, :turn_b }
RPG::UsableItem::Damage = ::Class.new unless defined?(RPG::UsableItem::Damage)
RPG::UsableItem::Damage.class_eval { attr_accessor :type, :element_id, :formula, :variance, :critical }
RPG::UsableItem::Effect = ::Class.new unless defined?(RPG::UsableItem::Effect)
RPG::UsableItem::Effect.class_eval { attr_accessor :code, :data_id, :value1, :value2 }
RPG::Weapon = ::Class.new unless defined?(RPG::Weapon)
RPG::Weapon.class_eval { attr_accessor :description, :name, :icon_index, :price, :animation_id, :note, :id, :features, :params, :etype_id, :wtype_id }
class RPG::BaseItem
  attr_accessor :id, :name, :icon_index, :description, :features, :note
  def initialize
    @id, @name, @icon_index, @description, @features, @note = 0, '', 0, '', [], ''
  end
end
class RPG::BaseItem::Feature
  def initialize(code = 0, data_id = 0, value = 0)
    @code, @data_id, @value = code, data_id, value
  end
end
class RPG::UsableItem
  def for_opponent?; [1,2,3,4,5,6].include?(@scope); end
  def for_friend?; [7,8,9,10,11].include?(@scope); end
  def for_dead_friend?; [9,10].include?(@scope); end
  def for_user?; @scope == 11; end
  def for_one?; [1,3,7,9,11].include?(@scope); end
  def for_random?; [3,4,5,6].include?(@scope); end
  def for_all?; [2,8,10].include?(@scope); end
  def need_selection?; [1,7,9].include?(@scope); end
  def number_of_targets; for_random? ? @scope - 2 : 0; end
  def certain?; @hit_type == 0; end
  def physical?; @hit_type == 1; end
  def magical?; @hit_type == 2; end
  def battle_ok?; [0,1].include?(@occasion); end
  def menu_ok?; [0,2].include?(@occasion); end
end
class RPG::UsableItem::Damage
  def initialize
    @type, @element_id, @formula, @variance, @critical = 0, 0, '0', 20, false
  end
  def none?; @type == 0; end
  def to_hp?; [1,3,5].include?(@type); end
  def to_mp?; [2,4,6].include?(@type); end
  def recover?; [3,4].include?(@type); end
  def drain?; [5,6].include?(@type); end
  def sign; recover? ? -1 : 1; end
  def eval(a, b, v)
    [Kernel.eval(@formula), 0].max * sign
  rescue StandardError
    0
  end
end
class RPG::UsableItem::Effect
  def initialize(code = 0, data_id = 0, value1 = 0, value2 = 0)
    @code, @data_id, @value1, @value2 = code, data_id, value1, value2
  end
end
class RPG::Class
  def exp_for_level(level)
    basis, extra, acc_a, acc_b = @exp_params
    (basis * ((level - 1) ** (0.9 + acc_a / 250.0)) * level * (level + 1) /
      (6 + level ** 2 / 50.0 / acc_b) + (level - 1) * extra).round
  end
end
class RPG::Map
  def scroll_horizontal?; [2,3].include?(@scroll_type); end
  def scroll_vertical?; [1,3].include?(@scroll_type); end
end
class RPG::System
  def japanese?; @japanese; end
end
class RPG::EventCommand
  def initialize(code = 0, indent = 0, parameters = [])
    @code, @indent, @parameters = code, indent, parameters
  end
end
class RPG::MoveCommand
  def initialize(code = 0, parameters = [])
    @code, @parameters = code, parameters
  end
end
class RPG::MoveRoute
  def initialize
    @repeat, @skippable, @wait, @list = true, false, false, [RPG::MoveCommand.new]
  end
end
[RPG::BGM, RPG::BGS].each do |klass|
  channel = klass == RPG::BGM ? :bgm : :bgs
  klass.class_eval do
    attr_accessor :pos
    define_method(:initialize) do |name = '', volume = 100, pitch = 100|
      super(name, volume, pitch)
      @pos = 0
    end
    define_method(:play) do |pos = 0|
      if @name.empty?
        Audio.public_send("#{channel}_stop")
        self.class.instance_variable_set(:@last, self.class.new)
      else
        Audio.public_send("#{channel}_play", "Audio/#{channel.to_s.upcase}/#{@name}", @volume, @pitch, pos)
        self.class.instance_variable_set(:@last, clone)
      end
    end
    define_method(:replay) { play(@pos || 0) }
    define_singleton_method(:last) do
      value = (@last || new).clone
      value.pos = Audio.public_send("#{channel}_pos")
      value
    end
    define_singleton_method(:stop) do
      Audio.public_send("#{channel}_stop")
      @last = new
    end
    define_singleton_method(:fade) { |time| Audio.public_send("#{channel}_fade", time); @last = new }
  end
end
[RPG::ME, RPG::SE].each do |klass|
  channel = klass == RPG::ME ? :me : :se
  klass.class_eval do
    define_method(:play) do
      Audio.public_send("#{channel}_play", "Audio/#{channel.to_s.upcase}/#{@name}", @volume, @pitch) unless @name.empty?
    end
    define_singleton_method(:stop) { Audio.public_send("#{channel}_stop") }
  end
end
class RPG::ME
  def self.fade(time); Audio.me_fade(time); end
end
class RPG::CommonEvent
  def autorun?; @trigger == 1; end
  def parallel?; @trigger == 2; end
end
class RPG::Skill
  def skill?; true; end
  def item?; false; end
end
class RPG::Item
  def skill?; false; end
  def item?; true; end
  def key_item?; @itype_id == 2; end
end
class RPG::Weapon
  def performance; @params[2] + @params[4] + @params.inject(0,:+); end
end
class RPG::Armor
  def performance; @params[3] + @params[5] + @params.inject(0,:+); end
end
