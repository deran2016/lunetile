// Passive API-boundary observation of the generated-tone probe; no hooks replace return values.
const root = Process.mainModule.path.replace(/[\\/][^\\/]+$/, '');
const trace = new File(root + '/audio-api.jsonl', 'w');
const seen = new Set();
let count = 0;
function record(kind, data = {}) {
  if (count++ >= 10000) return;
  trace.write(JSON.stringify({kind, time_ms: Date.now(), ...data}) + '\n');
  trace.flush();
}
function guid(pointer) {
  const hex = (number, width) => number.toString(16).padStart(width, '0');
  let tail = '';
  for (let i = 8; i < 16; ++i) tail += hex(pointer.add(i).readU8(), 2);
  return [hex(pointer.readU32(),8),hex(pointer.add(4).readU16(),4),hex(pointer.add(6).readU16(),4),tail.slice(0,4),tail.slice(4)].join('-');
}
function attach(address, name, callbacks) {
  if (!address || seen.has(address.toString())) return;
  seen.add(address.toString());
  Interceptor.attach(address, callbacks);
  record('hook', {name, address: address.toString()});
}
function method(object, index) { return object.readPointer().add(index * Process.pointerSize).readPointer(); }
function segmentConfiguration(object){
  const iid=Memory.alloc(16),output=Memory.alloc(Process.pointerSize);
  iid.writeByteArray([0x88,0x44,0x78,0xc6,0xa3,0x41,0x8f,0x41,0xaa,0x15,0xb3,0x50,0x93,0xba,0x42,0xd4]);
  if(new NativeFunction(method(object,0),'int',['pointer','pointer','pointer'],'stdcall')(object,iid,output)!==0)return;
  const segment=output.readPointer();
  attach(method(segment,19),'IDirectMusicSegment.SetParam',{onEnter(args){record('segment-param',{object:args[0].toString(),guid:guid(args[1]),groups:args[2].toUInt32(),index:args[3].toUInt32(),time:args[4].toInt32(),value:args[5].toString()});}});
  for(const [name,index] of [['repeats',6],['resolution',8],['start-point',21]])attach(method(segment,index),'segment-'+name,{onEnter(args){record('segment-'+name,{object:args[0].toString(),value:args[1].toUInt32()});}});
  attach(method(segment,23),'IDirectMusicSegment.SetLoopPoints',{onEnter(args){record('segment-loops',{object:args[0].toString(),start:args[1].toInt32(),end:args[2].toInt32()});}});
  attach(method(segment,26),'IDirectMusicSegment8.SetTrackConfig',{onEnter(args){record('segment-track-config',{object:args[0].toString(),class:guid(args[1]),groups:args[2].toUInt32(),index:args[3].toUInt32(),on:args[4].toUInt32(),off:args[5].toUInt32()});}});
  for(const [name,index] of [['download',29],['unload',30]])attach(method(segment,index),'segment-'+name,{onEnter(args){record('segment-'+name,{object:args[0].toString(),path:args[1].toString()});}});
  new NativeFunction(method(segment,2),'uint',['pointer'],'stdcall')(segment);
}
function musicCore(object){
  attach(method(object,5),'IDirectMusic.CreatePort',{
    onEnter(args){const p=args[2],size=p.readU32();const row={class:guid(args[1]),size};if(size>=32){Object.assign(row,{valid:p.add(4).readU32(),voices:p.add(8).readU32(),groups:p.add(12).readU32(),channels:p.add(16).readU32(),rate:p.add(20).readU32(),effects:p.add(24).readU32(),share:p.add(28).readU32()});if(size>=36)row.features=p.add(32).readU32();}record('create-port',row);}
  });
}
function performance(object) {
  for(const [name,index] of [['prepare-time',7],['bumper-length',9]])attach(method(object,index),name,{onEnter(args){record(name,{object:args[0].toString(),milliseconds:args[1].toUInt32()});}});
  attach(method(object,45),'IDirectMusicPerformance8.PlaySegmentEx',{
    onEnter(args){
      this.path=args[9];
      this.stateOutput=args[7];this.performance=args[0];
      try {
        const source=args[1],iid=Memory.alloc(16),output=Memory.alloc(Process.pointerSize);
        iid.writeByteArray([0xa2,0x29,0x60,0xf9,0x82,0x42,0xd2,0x11,0x87,0x17,0x00,0x60,0x08,0x93,0xb1,0xbd]);
        const query=new NativeFunction(method(source,0),'int',['pointer','pointer','pointer'],'stdcall');
        const row={object:args[0].toString(),source:source.toString(),flags:args[4].toUInt32(),start_time:((BigInt(args[6].toInt32())<<32n)|BigInt(args[5].toUInt32())).toString(),from:args[8].toString(),path:args[9].toString(),segment_query:query(source,iid,output)};
        if(row.segment_query===0){
          const segment=output.readPointer(),length=Memory.alloc(4),loopStart=Memory.alloc(4),loopEnd=Memory.alloc(4),repeats=Memory.alloc(4);
          const getLength=new NativeFunction(method(segment,3),'int',['pointer','pointer'],'stdcall');
          row.length_result=getLength(segment,length);if(row.length_result===0)row.length_ticks=length.readS32();
          row.loop_result=new NativeFunction(method(segment,24),'int',['pointer','pointer','pointer'],'stdcall')(segment,loopStart,loopEnd);
          if(row.loop_result===0){row.loop_start_ticks=loopStart.readS32();row.loop_end_ticks=loopEnd.readS32();}
          row.repeats_result=new NativeFunction(method(segment,5),'int',['pointer','pointer'],'stdcall')(segment,repeats);
          if(row.repeats_result===0)row.repeats=repeats.readU32();
          row.start_point_result=new NativeFunction(method(segment,22),'int',['pointer','pointer'],'stdcall')(segment,length);
          if(row.start_point_result===0)row.start_point_ticks=length.readS32();
          new NativeFunction(method(segment,2),'uint',['pointer'],'stdcall')(segment);
        }
        record('play-segment',row);
      }catch(error){record('read-error',{message:String(error)});}
    },
    onLeave(result){if(result.toInt32()===0){
      if(!this.path.isNull())inspectPathBuffers(this.path);
      let state=null,release=false;
      if(!this.stateOutput.isNull())state=this.stateOutput.readPointer();
      else{
        const time=Memory.alloc(4),reference=Memory.alloc(8),output=Memory.alloc(Process.pointerSize);
        const timeResult=new NativeFunction(method(this.performance,15),'int',['pointer','pointer','pointer'],'stdcall')(this.performance,reference,time);
        if(timeResult===0){
          const now=time.readS32(),found=new NativeFunction(method(this.performance,6),'int',['pointer','pointer','int'],'stdcall')(this.performance,output,now+768);
          record('performance-position',{object:this.performance.toString(),now_ticks:now,query_ticks:now+768,result:found});
          if(found===0){state=output.readPointer();release=true;}
        }
      }
      if(state&&!state.isNull()){
        const value=Memory.alloc(4),row={object:this.performance.toString(),state:state.toString()};
        for(const [name,index] of [['start_ticks',5],['seek_ticks',6],['start_point_ticks',7]]){const hr=new NativeFunction(method(state,index),'int',['pointer','pointer'],'stdcall')(state,value);row[name+'_result']=hr;if(hr===0)row[name]=value.readS32();}record('segment-state',row);
        if(release)new NativeFunction(method(state,2),'uint',['pointer'],'stdcall')(state);
      }
    }}
  });
  attach(method(object,46),'IDirectMusicPerformance8.StopEx',{
    onEnter(args){record('stop-segment',{object:args[0].toString(),source:args[1].toString()});}
  });
  attach(method(object,5),'IDirectMusicPerformance.Stop',{
    onEnter(args){record('stop-base',{object:args[0].toString(),segment:args[1].toString(),state:args[2].toString(),music_time:args[3].toInt32(),flags:args[4].toUInt32()});}
  });
  const playing=new Map();
  attach(method(object,14),'IDirectMusicPerformance.IsPlaying',{
    onEnter(args){this.object=args[0].toString();this.source=args[1].toString();this.state=args[2].toString();},
    onLeave(result){const key=this.object+','+this.source+','+this.state,value=result.toInt32();if(playing.get(key)!==value){playing.set(key,value);record('is-playing',{object:this.object,source:this.source,state:this.state,result:value});}}
  });
  attach(method(object,44),'IDirectMusicPerformance8.InitAudio',{
    onEnter(args){
      const parameters=args[7];let audio=null;
      if(!parameters.isNull()){
        const size=parameters.readU32();audio={size};
        if(size>=40)audio={size,initialize_now:parameters.add(4).readU32(),valid:parameters.add(8).readU32(),features:parameters.add(12).readU32(),voices:parameters.add(16).readU32(),sample_rate:parameters.add(20).readU32()};
      }
      record('init-audio',{default_path:args[4].toUInt32(),channels:args[5].toUInt32(),flags:args[6].toUInt32(),parameters:audio});
    }
  });
  // IDirectMusicPerformance / Performance8 SetGlobalParam is vtable entry 34.
  attach(method(object,34),'IDirectMusicPerformance.SetGlobalParam',{
    onEnter(args) {
      try {
        const size=args[3].toUInt32();
        record('global-param',{object:args[0].toString(),guid:guid(args[1]),size,
          integer:size===4?args[2].readS32():null, float:size===4?args[2].readFloat():null});
      } catch(error) { record('read-error',{message:String(error)}); }
    }
  });
  attach(method(object,11),'IDirectMusicPerformance.SendPMsg',{
    onEnter(args){try{const p=args[1],size=p.readU32(),type=p.add(40).readU32();
      const row={object:args[0].toString(),size,type,channel:p.add(24).readU32()};
      if(type===4&&size>=64)row.tempo=p.add(56).readDouble();
      if(type===5&&size>=84){row.start=p.add(68).readS16();row.end=p.add(70).readS16();row.curve_type=p.add(80).readU8();row.cc=p.add(82).readU8();}
      if(type===8&&size>=60)row.transpose=p.add(56).readS16();
      if(type===1&&size>=77){row.duration=p.add(56).readS32();row.note=p.add(75).readU8();row.transpose=p.add(76).readS8();}
      if(type===1||type===4||type===8||(type===5&&row.channel===0))record('pmsg',row);
    }catch(error){record('read-error',{message:String(error)});}}
  });
  attach(method(object,49),'IDirectMusicPerformance8.CreateStandardAudioPath',{
    onEnter(args){this.output=args[4];record('create-standard-path',{type:args[1].toUInt32(),channels:args[2].toUInt32(),active:args[3].toUInt32()});},
    onLeave(result){if(result.toInt32()===0)try{audioPath(this.output.readPointer());}catch(error){record('read-error',{message:String(error)});}}
  });
  attach(method(object,48),'IDirectMusicPerformance8.CreateAudioPath',{
    onEnter(args){this.output=args[3];},
    onLeave(result){if(result.toInt32()===0)try{audioPath(this.output.readPointer());}catch(error){record('read-error',{message:String(error)});}}
  });
}
function audioPath(object){
  attach(method(object,5),'IDirectMusicAudioPath.SetVolume',{
    onEnter(args){record('path-volume',{object:args[0].toString(),volume:args[1].toInt32(),duration:args[2].toUInt32()});}
  });
  attach(method(object,3),'IDirectMusicAudioPath.GetObjectInPath',{
    onEnter(args){this.iid=guid(args[6]);this.output=args[7];this.channel=args[1].toUInt32();this.stage=args[2].toUInt32();this.buffer=args[3].toUInt32();this.object_guid=guid(args[4]);},
    onLeave(result){if(result.toInt32()===0)try{
      record('path-object',{iid:this.iid,channel:this.channel,stage:this.stage,buffer:this.buffer,object_guid:this.object_guid});
      if(this.iid==='279afa85-4981-11ce-a521-0020af0be560'||this.iid==='6825a449-7524-4d82-920f-50e36ab3ab1e')soundBuffer(this.output.readPointer());
    }catch(error){record('read-error',{message:String(error)});}}
  });
}
function inspectPathBuffers(object){
  const objectGuid=Memory.alloc(16),iid=Memory.alloc(16),output=Memory.alloc(Process.pointerSize);
  objectGuid.writeByteArray(Array(16).fill(0));
  iid.writeByteArray([0x49,0xa4,0x25,0x68,0x24,0x75,0x82,0x4d,0x92,0x0f,0x50,0xe3,0x6a,0xb3,0xab,0x1e]);
  const get=new NativeFunction(method(object,3),'int',['pointer','uint','uint','uint','pointer','uint','pointer','pointer'],'stdcall');
  for(let index=0;index<4;++index){
    const result=get(object,0xfffffffb,0x6000,index,objectGuid,0,iid,output);
    record('path-buffer-probe',{path:object.toString(),index,result});
    if(result===0){const buffer=output.readPointer();soundBuffer(buffer);new NativeFunction(method(buffer,2),'uint',['pointer'],'stdcall')(buffer);}
  }
}
function soundBuffer(object) {
  const caps=Memory.alloc(20);caps.writeU32(20);
  const capsResult=new NativeFunction(method(object,3),'int',['pointer','pointer'],'stdcall')(object,caps);
  if(capsResult===0)record('ds-caps',{object:object.toString(),flags:caps.add(4).readU32(),buffer_bytes:caps.add(8).readU32()});
  const bufferIid=Memory.alloc(16),bufferOutput=Memory.alloc(Process.pointerSize);
  bufferIid.writeByteArray([0x49,0xa4,0x25,0x68,0x24,0x75,0x82,0x4d,0x92,0x0f,0x50,0xe3,0x6a,0xb3,0xab,0x1e]);
  const bufferQuery=new NativeFunction(method(object,0),'int',['pointer','pointer','pointer'],'stdcall')(object,bufferIid,bufferOutput);
  if(bufferQuery===0){
    const buffer8=bufferOutput.readPointer(),effectClass=Memory.alloc(16),effectIid=Memory.alloc(16),effectOutput=Memory.alloc(Process.pointerSize);
    effectClass.writeByteArray([0x71,0x5e,0x98,0xef,0xc7,0xd5,0xd4,0x42,0xba,0x4d,0x2d,0x07,0x3e,0x2e,0x96,0xf4]);
    effectIid.writeByteArray([0x6a,0x6a,0x16,0x4b,0x66,0x0d,0xf3,0x43,0x80,0xe3,0xee,0x62,0x80,0xde,0xe1,0xa4]);
    const found=new NativeFunction(method(buffer8,23),'int',['pointer','pointer','uint','pointer','pointer'],'stdcall')(buffer8,effectClass,0,effectIid,effectOutput);
    record('ds-reverb-query',{object:object.toString(),result:found});
    if(found===0){
      const effect=effectOutput.readPointer(),parameters=Memory.alloc(48);
      const result=new NativeFunction(method(effect,4),'int',['pointer','pointer'],'stdcall')(effect,parameters);
      if(result===0)record('ds-reverb-parameters',{room:parameters.readS32(),room_hf:parameters.add(4).readS32(),rolloff:parameters.add(8).readFloat(),decay:parameters.add(12).readFloat(),decay_hf:parameters.add(16).readFloat(),reflections:parameters.add(20).readS32(),reflections_delay:parameters.add(24).readFloat(),reverb:parameters.add(28).readS32(),reverb_delay:parameters.add(32).readFloat(),diffusion:parameters.add(36).readFloat(),density:parameters.add(40).readFloat(),hf_reference:parameters.add(44).readFloat()});
      new NativeFunction(method(effect,2),'uint',['pointer'],'stdcall')(effect);
    }
    effectClass.writeByteArray([0x68,0x02,0xfc,0x87,0x55,0x9a,0x60,0x43,0x95,0xaa,0x00,0x4a,0x1d,0x9d,0xe2,0x6c]);
    effectIid.writeByteArray([0x3a,0x8c,0x85,0x46,0xc6,0x0d,0xe3,0x45,0xb7,0x60,0xd4,0xee,0xf1,0x6c,0xb3,0x25]);
    const waves=new NativeFunction(method(buffer8,23),'int',['pointer','pointer','uint','pointer','pointer'],'stdcall')(buffer8,effectClass,0,effectIid,effectOutput);
    record('ds-waves-reverb-query',{object:object.toString(),result:waves});
    if(waves===0){
      const effect=effectOutput.readPointer(),parameters=Memory.alloc(16);
      const result=new NativeFunction(method(effect,4),'int',['pointer','pointer'],'stdcall')(effect,parameters);
      if(result===0)record('ds-waves-reverb-parameters',{input_gain:parameters.readFloat(),mix:parameters.add(4).readFloat(),time:parameters.add(8).readFloat(),hf_ratio:parameters.add(12).readFloat()});
      new NativeFunction(method(effect,2),'uint',['pointer'],'stdcall')(effect);
    }
    new NativeFunction(method(buffer8,2),'uint',['pointer'],'stdcall')(buffer8);
  }
  const format=Memory.alloc(64),written=Memory.alloc(4);
  const getFormat=new NativeFunction(method(object,5),'int',['pointer','pointer','uint','pointer'],'stdcall');
  const result=getFormat(object,format,64,written);
  if(result===0)record('ds-format',{object:object.toString(),bytes:written.readU32(),tag:format.readU16(),channels:format.add(2).readU16(),sample_rate:format.add(4).readU32(),bits:format.add(14).readU16()});
  attach(method(object,17),'IDirectSoundBuffer.SetFrequency',{
    onEnter(args){record('ds-frequency',{object:args[0].toString(),frequency:args[1].toUInt32()});}
  });
  attach(method(object,15),'IDirectSoundBuffer.SetVolume',{
    onEnter(args){record('ds-volume',{object:args[0].toString(),volume:args[1].toInt32()});}
  });
}
function soundDevice(object) {
  attach(method(object,3),'IDirectSound.CreateSoundBuffer',{
    onEnter(args){this.output=args[2];},
    onLeave(result){if(result.toInt32()===0)try{soundBuffer(this.output.readPointer());}catch(error){record('read-error',{message:String(error)});}}
  });
}
globalThis.audioObserver = Process.attachModuleObserver({
  onAdded(module) {
    const name=module.name.toLowerCase();
    if(name==='rgss104e.dll')record('runtime',{path:module.path,base:module.base.toString(),size:module.size});
    if (/^(dmusic|dmime|dmsynth|dsound|winmm|quartz|ole32|combase)\.dll$/.test(name))record('module',{name});
    if(name==='ole32.dll'||name==='combase.dll'){
      attach(module.findExportByName('CoCreateInstance'),'CoCreateInstance',{
        onEnter(args){this.clsid=guid(args[0]);this.iid=guid(args[3]);this.output=args[4];},
        onLeave(result){
          if(this.clsid!=='00000323-0000-0000-c000-000000000046')record('com-create',{clsid:this.clsid,iid:this.iid,result:result.toInt32()});
          if(result.toInt32()===0)try{
            if(this.clsid==='d2ac2881-b39b-11d1-8704-00600893b1bd')performance(this.output.readPointer());
            if(this.clsid==='d2ac2882-b39b-11d1-8704-00600893b1bd')segmentConfiguration(this.output.readPointer());
            if(this.clsid==='636b9f10-0c7d-11d1-95b2-0020afdc7421')musicCore(this.output.readPointer());
          }catch(error){record('read-error',{message:String(error)});}
        }
      });
    }
    if(name==='dsound.dll')for(const entry of ['DirectSoundCreate','DirectSoundCreate8']){
      attach(module.findExportByName(entry),entry,{
        onEnter(args){this.output=args[1];},
        onLeave(result){if(result.toInt32()===0)try{soundDevice(this.output.readPointer());}catch(error){record('read-error',{message:String(error)});}}
      });
    }
    if(name==='winmm.dll')for(const entry of ['midiOutOpen','midiStreamOpen','midiOutShortMsg','midiOutSetVolume','midiOutSetPitch','midiOutSetPlaybackRate','midiStreamProperty','waveOutSetPitch','waveOutSetPlaybackRate']){
      attach(module.findExportByName(entry),entry,{
        onEnter(args){record('winmm',{name:entry,first:args[0].toString(),second:args[1].toUInt32(),third:args[2].toUInt32()});}
      });
    }
  }
});
record('armed',{pid:Process.id,pointer_size:Process.pointerSize});
const begin=new File(root+'/begin-trace.txt','w');begin.write('Passive audio hooks armed');begin.close();
send({armed:true,pid:Process.id});
