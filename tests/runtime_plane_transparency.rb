class ReferencePlane < RGSSXP::DisplayObject
  attr_accessor :bitmap
  def emit(commands)
    return unless @bitmap && !@bitmap.disposed? && @zoom_x > 0 && @zoom_y > 0
    area = @viewport ? @viewport.rect : Rect.new(0, 0, Graphics.width, Graphics.height)
    w, h = @bitmap.width * @zoom_x, @bitmap.height * @zoom_y
    start_x, start_y = area.x - @ox % w, area.y - @oy % h
    y = start_y
    while y < area.y + area.height
      x = start_x
      while x < area.x + area.width
        RGSSXP.quad(commands, @bitmap, x, y, @bitmap.rect, zoom_x: @zoom_x, zoom_y: @zoom_y,
          opacity: @opacity, blend: @blend_type, color: @color, tone: @tone, clip: area)
        x += w
      end
      y += h
    end
  end
end

# Shared XP/VXA cache invalidation and Plane rendering regression.
b = Bitmap.new(2,2)
raise 'empty alpha' unless b.__transparent?
plane = Plane.new
reference = ReferencePlane.new
plane.bitmap = reference.bitmap = b
commands=[]; plane.emit(commands)
raise 'empty plane emitted' unless commands.empty?
b.set_pixel(1,1,Color.new(255,0,0,1))
raise 'pixel invalidation' if b.__transparent?
b.clear
raise 'clear invalidation' unless b.__transparent?
source=Bitmap.new(2,2)
source.fill_rect(source.rect,Color.new(0,255,0,255))
b.blt(0,0,source,source.rect)
raise 'blt invalidation' if b.__transparent?
b.clear
b.stretch_blt(b.rect,source,source.rect)
raise 'stretch invalidation' if b.__transparent?
b.clear
b.draw_text(0,0,2,2,'X')
b.clear
raise 'text/clear invalidation' unless b.__transparent?
# A single repeated source rect must preserve offsets, clipping and blend modes.
b.fill_rect(b.rect,Color.new(23,56,89,255))
[plane,reference].each { |node| node.zoom_x=node.zoom_y=80; node.ox=13; node.oy=19 }
[0,1,2].each do |blend|
 plane.blend_type=reference.blend_type=blend
 capture = lambda do |node|
  commands=[]; node.emit(commands)
  Graphics.__present(commands,-1.0,nil,0.0)
  [[0,0],[17,21],[159,159],[170,190]].map { |x,y| Graphics.__scene_pixel(x,y) }
 end
 raise 'plane pixel mismatch' unless capture.call(plane) == capture.call(reference)
 b.clear
 raise 'transparent plane pixels changed' unless capture.call(plane) == capture.call(reference)
 b.fill_rect(b.rect,Color.new(23,56,89,255))
end
b.dispose
commands=[]; plane.emit(commands)
raise 'disposed plane emitted' unless commands.empty?
plane.dispose;reference.dispose;source.dispose
File.write('runtime-complete.txt',"plane transparency PASS,#{$DEBUG},#{$BTEST}")
