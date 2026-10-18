bitmap = Bitmap.new(640,480)
bitmap.fill_rect(bitmap.rect, Color.new(20,40,60))
sprite = Sprite.new
sprite.bitmap = bitmap
20.times { Graphics.update }
File.write('cpu-sample-ready.txt','ready')
240.times { Graphics.update }
File.write('runtime-complete.txt','cpu,false,false')
sprite.dispose
bitmap.dispose
