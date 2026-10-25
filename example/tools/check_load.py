"""Isolated Windows TCP load check. Never reads or changes existing accounts."""
import argparse,concurrent.futures,ctypes,hashlib,json,os,select,shutil,socket,struct,subprocess,tempfile,threading,time
from pathlib import Path
from smoke_test import start_server,stop

def receive(sock):
 def exact(n):
  chunks=[]
  while n:
   b=sock.recv(n)
   if not b:raise EOFError('connection closed')
   chunks.append(b);n-=len(b)
  return b''.join(chunks)
 size=struct.unpack('!I',exact(4))[0]
 if not 0<size<=262144:raise ValueError('invalid frame')
 return json.loads(exact(size)),size+4
def transmit(sock,msg):
 data=json.dumps(msg,separators=(',',':')).encode();sock.sendall(struct.pack('!I',len(data))+data)
 return receive(sock)
def percentile(xs,p):return sorted(xs)[min(len(xs)-1,int(len(xs)*p))] if xs else None
def sample_process(process):
 class Counters(ctypes.Structure):
  _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong),('peak_ws',ctypes.c_size_t),('ws',ctypes.c_size_t),('peak_pool',ctypes.c_size_t),('pool',ctypes.c_size_t),('peak_nonpaged',ctypes.c_size_t),('nonpaged',ctypes.c_size_t),('pagefile',ctypes.c_size_t),('peak_pagefile',ctypes.c_size_t)]
 c=Counters();c.cb=ctypes.sizeof(c);ctypes.windll.psapi.GetProcessMemoryInfo(int(process._handle),ctypes.byref(c),c.cb)
 times=[ctypes.c_ulonglong() for _ in range(4)];ctypes.windll.kernel32.GetProcessTimes(int(process._handle),*[ctypes.byref(t) for t in times])
 return {'wall':time.monotonic(),'cpu_s':(times[2].value+times[3].value)/1e7,'working_set':c.ws,'private_bytes':c.pagefile}

def check(bundle,output,clients,duration,protocol,mode='idle',stress=False,metrics=False,local_disk=False,previews=False):
 bundle=bundle.resolve();output=output.resolve()
 if output.exists() or output.is_relative_to(bundle) or bundle.is_relative_to(output):raise ValueError('Use a new isolated output')
 temporary=Path(tempfile.mkdtemp(prefix='lunetile-load-')).resolve() if local_disk else None
 if temporary:assert temporary.is_relative_to(Path(tempfile.gettempdir()).resolve());output.mkdir(parents=True)
 server=(temporary if temporary else output)/'server';shutil.copytree(bundle/'server/data',server/'data');shutil.copy2(bundle/'server/lunetile-mmo-server.exe',server/'lunetile-mmo-server.exe')
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 config=json.loads((server/'data/server.json').read_text(encoding='utf-8'));config.update(bind=f'127.0.0.1:{port}',max_clients=32)
 (server/'data/server.json').write_text(json.dumps(config),encoding='utf-8')
 monsters=json.loads((server/'data/monsters.json').read_text(encoding='utf-8'))
 if mode=='idle':
  for m in monsters:m['spawns']=[]
 elif stress:
  spawn=config['spawn']
  for m in monsters:m['spawns']=[]
  monsters[0]['spawns']=[dict(map_id=spawn['map_id'],x=12+i%16,y=3+i//16) for i in range(64)]
 (server/'data/monsters.json').write_text(json.dumps(monsters),encoding='utf-8')
 reports=[];errors=[];memory=[];identities={};ready=threading.Barrier(clients+1);begin=threading.Event();finish=threading.Event()
 def bot(i):
  samples={k:[] for k in ['poll','move','attack','service']};received=0;notices={};seq=0;step=0;next_service=0;invited=-1;event_cursor=0;experience_events=0;trade_completions=0;talked=False;preview_ms=0;preview_step=0;preview_epoch=0;preview_count=0;history=[];extra_frames=0
  try:
   with socket.create_connection(('127.0.0.1',port),timeout=5) as sock:
    sock.settimeout(5);sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
    welcome,n=transmit(sock,dict(type='register',protocol=protocol,name=f'Load{i}'));received+=n
    if welcome['type']!='welcome':raise ValueError(welcome)
    state=welcome['state'];identities[i]=welcome['id'];ready.wait(timeout=30);begin.wait()
    start=time.monotonic();deadline=start+duration;next_poll=start;next_move=start;next_attack=start
    while time.monotonic()<deadline and not finish.is_set():
     # Preview rejection is an unsolicited state, not a reply to the next command.
     while select.select([sock],[],[],0)[0]:state,n=receive(sock);received+=n;extra_frames+=1
     now=time.monotonic();kind='poll';msg={'type':'poll'}
     service_phase=mode=='mixed' and (now-start)%12>=10
     social=state.get('social',{});trade=social.get('trade');invite=social.get('invite');action=None;key='';amount=0;revision=0
     if service_phase and now>=next_service:
      if trade:
       own=trade['offers'][identities[i]]
       if not own['items'] and state['inventory'].get('potion',0)>0:action='trade_item';key='potion';amount=1
       elif all(o['items'] for o in trade['offers'].values()) and identities[i] not in trade['confirmed']:action='trade_confirm';revision=trade['revision']
      elif invite and invite['kind']=='trade_invite':action='accept'
      elif i%2==0 and i+1<clients and invited!=int((now-start)//12):action='trade_invite';key=identities[i+1];invited=int((now-start)//12)
     if action:
      msg=dict(type='social',action=action,key=key,amount=amount,text='',revision=revision);kind='service';next_service=now+.2
     elif service_phase and not talked and any(abs(n['position']['x']-state['self']['position']['x'])+abs(n['position']['y']-state['self']['position']['y'])<=1 for n in state.get('npcs',[])):
      npc=next(n for n in state['npcs'] if abs(n['position']['x']-state['self']['position']['x'])+abs(n['position']['y']-state['self']['position']['y'])<=1);msg=dict(type='talk',npc_id=npc['id']);kind='service';talked=True
     elif mode!='idle' and not service_phase and state['self']['hp']>0 and now>=next_move:
      motion=state['self']['motion'];direction=[6,2,4,8][step//5%4];seq+=1;step+=1
      msg=dict(type='move',seq=seq,origin=[motion['x'],motion['y']],epoch=motion['epoch'],parts=[dict(direction=direction,ms=200)]);kind='move';next_move=now+.2
     elif mode!='idle' and not service_phase and now>=next_attack:
      msg=dict(type='attack',skill_id='basic',direction=[6,2,4,8][i%4]);kind='attack';next_attack=now+.65
     elif now<next_poll:
      time.sleep(min(.002,next_poll-now));continue
     else:next_poll=max(next_poll+1/30,now+.001)
     if previews and state['self']['hp']>0 and kind in ['move','poll']:
      motion=state['self']['motion']
      if motion['epoch']!=preview_epoch:preview_epoch=motion['epoch'];preview_ms=preview_step=0;history=[]
      if kind=='move':preview_ms+=200;preview_step+=1;history.append(([motion['x'],motion['y']],dict(step=preview_step,**msg['parts'][0])));history=history[-3:]
      preview=dict(type='preview',origin=history[0][0] if history else [motion['x'],motion['y']],epoch=preview_epoch,elapsed=preview_ms,parts=[p for _,p in history],moving=kind=='move',direction=msg['parts'][0]['direction'] if kind=='move' else state['self']['direction'])
      data=json.dumps(preview,separators=(',',':')).encode();sock.sendall(struct.pack('!I',len(data))+data);preview_count+=1
     began=time.perf_counter();state,n=transmit(sock,msg);last_frame=time.perf_counter();received+=n
     while kind=='move' and state.get('move_ack',{}).get('seq',0)<seq:
      state,n=receive(sock);received+=n;last_frame=time.perf_counter();extra_frames+=1
     while select.select([sock],[],[],.002)[0]:state,n=receive(sock);received+=n;last_frame=time.perf_counter();extra_frames+=1
     elapsed=(last_frame-began)*1000
     if kind=='move' and not state.get('move_ack',{}).get('accepted'):history=[]
     if state.get('type')!='state':raise ValueError(state.get('type'))
     if state.get('notice'):notices[state['notice']]=notices.get(state['notice'],0)+1
     if state.get('notice')=='거래 완료':trade_completions+=1
     experience_events+=sum(e.get('kind')=='experience' and e.get('seq',0)>event_cursor for e in state.get('events',[]));event_cursor=max(event_cursor,state.get('event_seq',0))
     samples[kind].append(elapsed)
    reports.append({'client':i,'bytes':received,'notices':notices,'extra_frames':extra_frames,'previews':preview_count,'experience_events':experience_events,'trade_completions':trade_completions,'timings':{k:{'count':len(v),'p50':percentile(v,.5),'p95':percentile(v,.95),'p99':percentile(v,.99),'max':max(v,default=None)} for k,v in samples.items()}})
    return samples
  except Exception as e:
   errors.append({'client':i,'error':str(e),'notices':notices,'previews':preview_count,'extra_frames':extra_frames});print('load client failure',i,str(e),flush=True);finish.set();ready.abort();return samples
 process=None
 with (output/'server.log').open('wb') as log:
  try:
   exe=server/'lunetile-mmo-server.exe'
   if metrics:
    process=subprocess.Popen([str(exe),'--root',str(server),'--metrics',str(output/'metrics.jsonl')],stdout=log,stderr=log)
    end=time.monotonic()+10
    while time.monotonic()<end:
     try:
      with socket.create_connection(('127.0.0.1',port),timeout=.1):break
     except OSError:time.sleep(.05)
    else:raise TimeoutError('server startup')
   else:process=start_server(exe,server,port,log)
   with concurrent.futures.ThreadPoolExecutor(max_workers=clients) as pool:
    jobs=[pool.submit(bot,i) for i in range(clients)];ready.wait(timeout=40);before=sample_process(process);begin.set();start=time.monotonic();last=start
    while not all(j.done() for j in jobs):
     if process.poll() is not None:raise RuntimeError('server exited')
     if time.monotonic()-last>=1:memory.append(sample_process(process));last=time.monotonic()
     time.sleep(.05)
    after=sample_process(process);all_samples=[j.result() for j in jobs]
   total={k:[x for s in all_samples for x in s[k]] for k in ['poll','move','attack','service']}
   actual=after['wall']-before['wall']
   report={'clients':clients,'seconds':duration,'actual_seconds':actual,'mode':mode,'stress_64_monsters':stress,'preview_requests':previews,'protocol':protocol,'system_temp_disk':local_disk,'server_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'errors':errors,'bytes_per_second':sum(r['bytes'] for r in reports)/actual,
    'cpu_core_percent':(after['cpu_s']-before['cpu_s'])/(after['wall']-before['wall'])*100,'memory_samples':memory,
    'timings':{k:{'count':len(v),'p95':percentile(v,.95),'p99':percentile(v,.99),'max':max(v,default=None)} for k,v in total.items()},'peers':sorted(reports,key=lambda r:r['client'])}
   (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k not in ['memory_samples','peers']},ensure_ascii=False),flush=True)
   if errors:raise AssertionError(errors)
  finally:
   finish.set();begin.set();stop(process)
   if temporary:
    shutil.copytree(server,output/'server');assert temporary.is_relative_to(Path(tempfile.gettempdir()).resolve());shutil.rmtree(temporary)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('bundle',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--clients',type=int,default=32);p.add_argument('--seconds',type=float,default=60);p.add_argument('--protocol',type=int,default=11);p.add_argument('--mode',choices=['idle','mixed'],default='idle');p.add_argument('--stress',action='store_true');p.add_argument('--metrics',action='store_true');p.add_argument('--local-disk',action='store_true',help='Run server files in an isolated system-temp folder, archive then remove it');p.add_argument('--previews',action='store_true');a=p.parse_args();check(a.bundle,a.output,a.clients,a.seconds,a.protocol,a.mode,a.stress,a.metrics,a.local_disk,a.previews)
