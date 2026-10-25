module LunetileMMO
  class ParticleSystem
    # shortcut: crowded effects drop excess particles; raise budgets only after profiling.
    LIMIT=160;EMITTER_LIMIT=24
    SHAPES=%w[glow spark smoke ring drop flame].freeze
    Particle=Struct.new(:sprite,:born,:life,:x,:y,:vx,:vy,:gx,:gy,:size0,:size1,:spin,:rotation,:ramp,:ring,:color_step)
    def self.number?(v,min,max)
      v.is_a?(Numeric) && v.to_f.finite? && v>=min && v<=max
    end
    def self.pair?(v,min,max,ordered=false)
      v.is_a?(Array) && v.size==2 && v.all?{|n|number?(n,min,max)} && (!ordered || v[0]<=v[1])
    end
    def self.valid?(definitions)
      return false unless definitions.is_a?(Array) && definitions.size<=16
      ids=[]
      definitions.all? do |p|
        next false unless p.is_a?(Hash) && p['id'].is_a?(String) && p['id'].match?(/\A[a-z0-9_]{1,48}\z/) && !ids.include?(p['id'])
        ids<<p['id'];layers=p['layers']
        next false unless layers.is_a?(Array) && layers.size.between?(1,4)
        valid=layers.all? do |l|
          l.is_a?(Hash) && SHAPES.include?(l['shape']) && l['count'].is_a?(Integer) && l['count'].between?(1,48) &&
            %w[emit_ms delay_ms].all?{|k|l[k].is_a?(Integer)&&l[k].between?(0,1000)} &&
            pair?(l['life_ms'],50,3000,true) && l['life_ms'].all?{|v|v.is_a?(Integer)} && pair?(l['speed'],0,240,true) &&
            pair?(l['angle'],-720,720,true) && pair?(l['gravity'],-500,500) && pair?(l['size'],0.05,4) &&
            number?(l['spread'],0,96) && number?(l['spin'],-720,720) && [0,1].include?(l['blend']) &&
            l['z'].is_a?(Integer) && l['z'].between?(0,1200) && [true,false].include?(l['directional']) &&
            l['colors'].is_a?(Array) && l['colors'].size.between?(1,4) && l['colors'].all?{|c|c.is_a?(Array)&&c.size==3&&c.all?{|v|v.is_a?(Integer)&&v.between?(0,255)}}
        end
        valid && layers.sum{|l|l['count']}<=96
      end
    end
    def initialize
      @definitions=[];@presets={};@active=[];@emitters=[];@textures={}
      @spawned=@dropped=@peak=0;@by_preset=Hash.new(0)
      SHAPES.each{|shape|@textures[shape]=texture(shape)}
      @all=Array.new(LIMIT){Particle.new}
      @free=@all.dup
    end
    def texture(shape)
      b=Bitmap.new(32,32)
      32.times do |y|;32.times do |x|
        dx=(x-15.5)/16.0;dy=(y-15.5)/16.0;r=Math.sqrt(dx*dx+dy*dy)
        a=case shape
        when 'glow';(1-r).clamp(0,1)**2
        when 'smoke';(1-r).clamp(0,1)*0.65
        when 'ring';(1-(r-0.75).abs/0.12).clamp(0,1)
        when 'spark';[(1-dx.abs*8).clamp(0,1)*(1-dy.abs),(1-dy.abs*8).clamp(0,1)*(1-dx.abs)].max.clamp(0,1)
        when 'flame';((1-(x-15.5).abs/(4+y*0.28))*(1-(y-18).abs/18.0)).clamp(0,1)
        when 'drop';[(1-Math.sqrt(((x-15.5)/6)**2+((y-21)/7.0)**2)).clamp(0,1),y.between?(5,20) ? (1-(x-15.5).abs/[1,(y-4)*0.32].max).clamp(0,1)*0.8 : 0].max
        end
        b.fill_rect(x,y,1,1,Color.new(255,255,255,(a*255).to_i)) if a>0
      end;end
      b
    end
    def configure(definitions)
      return if @disposed
      definitions||=[];return if @definitions==definitions
      raise '파티클 JSON 정의를 확인하세요.' unless self.class.valid?(definitions)
      clear;@definitions=Marshal.load(Marshal.dump(definitions))
      @presets=@definitions.to_h do |p|
        layers=p['layers'].map do |layer|
          colors=layer['colors'];ramp=32.times.map do |i|
            index=i*(colors.size-1)/31.0;k=index.floor;t=index-k;a=colors[k];b=colors[[k+1,colors.size-1].min]
            Color.new(*3.times.map{|j|(a[j]+(b[j]-a[j])*t).round},255)
          end
          layer.merge('ramp'=>ramp)
        end
        [p['id'],layers]
      end
    end
    def emit(name,position,direction:6,source:nil,scale:1.0,intensity:1.0,seed:0)
      return false if @disposed || !@presets.key?(name)
      return false unless position.is_a?(Hash) && %w[x y].all?{|k|self.class.number?(position[k],-1_000_000,1_000_000)} &&
        [2,4,6,8].include?(direction) && self.class.number?(scale,0.1,3) && self.class.number?(intensity,0.1,2)
      if @emitters.size>=EMITTER_LIMIT;@dropped+=1;return false;end
      @emitters<<{layers:@presets[name],position:position.dup,direction:direction,source:source,scale:scale,intensity:intensity,
        began:LunetileMMO.now,rng:Random.new(seed),sent:Array.new(@presets[name].size,0)}
      @by_preset[name]+=1;true
    end
    def spawn(layer,emitter,born,now,avatars)
      rng=emitter[:rng];scale=emitter[:scale];life=(layer['life_ms'][0]+rng.rand*(layer['life_ms'][1]-layer['life_ms'][0]))/1000.0
      source=emitter[:source] && avatars[emitter[:source]];pos=emitter[:position]
      x=source ? source.real_x/4.0+16 : pos['x']*32+16;y=source ? source.real_y/4.0+16 : pos['y']*32+16
      if @free.empty? || now-born>=life || x-$game_map.display_x/4.0 < -192 || x-$game_map.display_x/4.0>Graphics.width+192 || y-$game_map.display_y/4.0 < -192 || y-$game_map.display_y/4.0>Graphics.height+192
        @dropped+=1;return
      end
      theta=rng.rand*Math::PI*2;radius=Math.sqrt(rng.rand)*layer['spread']*scale;x+=Math.cos(theta)*radius;y+=Math.sin(theta)*radius
      angle=layer['angle'][0]+rng.rand*(layer['angle'][1]-layer['angle'][0]);angle+={6=>0,2=>90,4=>180,8=>270}[emitter[:direction]] if layer['directional']
      radians=angle*Math::PI/180;speed=(layer['speed'][0]+rng.rand*(layer['speed'][1]-layer['speed'][0]))*scale
      p=@free.pop;p.born=born;p.life=life;p.x=x;p.y=y;p.vx=Math.cos(radians)*speed;p.vy=Math.sin(radians)*speed
      p.gx,p.gy=layer['gravity'];p.size0=layer['size'][0]*scale;p.size1=layer['size'][1]*scale;p.spin=layer['spin'];p.rotation=layer['shape']=='drop' ? -angle-90 : rng.rand*360
      p.ramp=layer['ramp'];p.ring=layer['shape']=='ring';p.color_step=nil
      unless p.sprite
        p.sprite=Sprite.new;p.sprite.ox=p.sprite.oy=16
      end
      s=p.sprite;s.bitmap=@textures[layer['shape']];s.blend_type=layer['blend'];s.z=layer['z'];s.angle=p.rotation
      render(p,now);s.visible=true
      @active<<p;@spawned+=1;@peak=[@peak,@active.size].max
    end
    def update(avatars={})
      return if @disposed || (@active.empty? && @emitters.empty?)
      now=LunetileMMO.now
      @camera_x=$game_map.display_x/4.0;@camera_y=$game_map.display_y/4.0
      @active.delete_if do |p|
        if now-p.born>=p.life;p.sprite.visible=false;@free<<p;true
        else
          render(p,now)
          false
        end
      end
      @emitters.delete_if do |e|
        complete=true;budget=32
        e[:layers].each_with_index do |layer,i|
          count=[(layer['count']*e[:intensity]).round,1].max;age=(now-e[:began])*1000-layer['delay_ms']
          due=age<0 ? 0 : layer['emit_ms']==0 ? count : [(age/layer['emit_ms']*count).floor,count].min
          amount=due-e[:sent][i];allowed=[amount,budget].min
          allowed.times do |j|
            born=e[:began]+layer['delay_ms']/1000.0+(layer['emit_ms']==0 ? 0 : (e[:sent][i]+j+1)*layer['emit_ms']/1000.0/count)
            spawn(layer,e,born,now,avatars)
          end
          @dropped+=amount-allowed;budget-=allowed;e[:sent][i]=due;complete=false if due<count
        end
        complete
      end
    end
    def render(p,now)
      age=now-p.born;q=(age/p.life).clamp(0,1);s=p.sprite
      s.x=p.x+p.vx*age+0.5*p.gx*age*age-@camera_x;s.y=p.y+p.vy*age+0.5*p.gy*age*age-@camera_y
      size=p.size0+(p.size1-p.size0)*q;s.zoom_x=size;s.zoom_y=size*(p.ring ? 0.42 : 1);s.opacity=(255*(1-q)**1.4).round
      s.angle=p.rotation+p.spin*age if p.spin!=0
      index=(q*31).to_i;if p.color_step!=index;s.color=p.ramp[index];p.color_step=index;end
    end
    def clear
      return if @disposed
      @active.each{|p|p.sprite.visible=false;@free<<p};@active.clear;@emitters.clear
    end
    def stats
      {active:@active.size,emitters:@emitters.size,peak:@peak,spawned:@spawned,dropped:@dropped,free:@free.size,by_preset:@by_preset.dup}
    end
    def dispose
      return if @disposed;clear;@all.each{|p|p.sprite&.dispose};@textures.each_value(&:dispose);@disposed=true
    end
  end
end
