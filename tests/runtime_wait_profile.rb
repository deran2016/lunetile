# Original-only diagnostic. The observer forwards each wait unchanged and is detached at exit.
module WaitProfile
  START=Win32API.new('RGSSWaitObserver','WaitObserveStart','','I')
  BEGIN_WAIT=Win32API.new('RGSSWaitObserver','WaitObserveBegin','','I')
  READ=Win32API.new('RGSSWaitObserver','WaitObserveRead','P','I')
  STOP=Win32API.new('RGSSWaitObserver','WaitObserveStop','','I')
  ROWS=[]
  raise 'Original wait observer rejected this runtime' unless START.call==1
end
module Graphics
  class << self
    alias update_without_wait_profile update
    def update
      raise 'Wait observer begin failed' unless WaitProfile::BEGIN_WAIT.call==1
      update_without_wait_profile
      buffer=[0.0]*5
      packed=buffer.pack('d*')
      raise 'Wait observer read failed' unless WaitProfile::READ.call(packed)==1
      WaitProfile::ROWS << [$bench_phase,$bench_frame]+packed.unpack('d*') if $bench_frame && $bench_frame>=80
    end
  end
end
def WaitProfile.finish
  raise 'Wait observer restoration failed' unless WaitProfile::STOP.call==1
  # A second attach checks that the exact original import target was restored.
  raise 'Restored wait import changed' unless WaitProfile::START.call==1 && WaitProfile::STOP.call==1
  File.open('wait-parts.csv','w') do |file|
    file.puts('stage,frame,wait_ms,max_wait_ms,calls,timeouts,messages')
    WaitProfile::ROWS.each { |row| file.puts(row.join(',')) }
  end
  File.open('wait-observer-restored.txt','w') { |file| file.write('original-import-restored') }
end
