// Passive timing observation of the owned replacement: no argument or return-value changes.
const root=Process.mainModule.path.replace(/[\\/][^\\/]+$/,'');
const output=new File(root+'/midi-timing.jsonl','w');
const seen=new Set(),clocks=new Set();let rows=0,masterClock=null,readingMaster=false;
function row(kind,details){if(rows++<6000){output.write(JSON.stringify({kind,wall_ms:Date.now(),...details})+'\n');output.flush();}}
function method(object,index){return object.readPointer().add(index*Process.pointerSize).readPointer();}
function hook(address,callbacks){if(address&&!seen.has(address.toString())){seen.add(address.toString());Interceptor.attach(address,callbacks);}}
function buffer(object){
 hook(method(object,5),{onEnter(args){row('midi-event',{buffer:args[0].toString(),reference_time:args[1].toUInt32()+args[2].toUInt32()*4294967296,message:args[4].toUInt32()});}});
}
function latencyClock(clock){
 clocks.add(clock.toString());
 hook(method(clock,3),{
  onEnter(args){this.object=args[0].toString();this.out=args[1];},
  onLeave(result){
   if(result.toInt32()!==0||!clocks.has(this.object)||readingMaster)return;
   let master=null;
   if(masterClock){
    readingMaster=true;
    try{
     const value=Memory.alloc(8),get=new NativeFunction(method(masterClock,3),'int',['pointer','pointer'],'stdcall');
     if(get(masterClock,value)===0)master=Number(value.readS64().toString());
    }finally{readingMaster=false;}
   }
   row('latency-clock',{object:this.object,reference_time:Number(this.out.readS64().toString()),master_reference_time:master});
  }
 });
}
function port(object){
 hook(method(object,3),{onEnter(args){
  const packet=args[1],data=Memory.alloc(Process.pointerSize),size=Memory.alloc(4),start=Memory.alloc(8);
  const raw=new NativeFunction(method(packet,9),'int',['pointer','pointer'],'stdcall');
  const used=new NativeFunction(method(packet,11),'int',['pointer','pointer'],'stdcall');
  const time=new NativeFunction(method(packet,10),'int',['pointer','pointer'],'stdcall');
  if(raw(packet,data)===0&&used(packet,size)===0&&time(packet,start)===0){const length=size.readU32();row('play-buffer',{buffer:packet.toString(),start:Number(start.readS64().toString()),bytes:length,raw:Array.from(new Uint8Array(data.readPointer().readByteArray(Math.min(length,256)))).map(x=>x.toString(16).padStart(2,'0')).join('')});}
 }});
 hook(method(object,6),{onEnter(args){this.began=Date.now();this.instrument=args[1].toString();},onLeave(result){row('download-instrument',{instrument:this.instrument,elapsed_ms:Date.now()-this.began,result:result.toInt32()});}});
 hook(method(object,8),{onEnter(args){this.out=args[1];},onLeave(result){if(result.toInt32()===0)latencyClock(this.out.readPointer());}});
}
function path(object){
 hook(method(object,3),{onEnter(args){this.stage=args[2].toUInt32();this.out=args[7];},onLeave(result){if(result.toInt32()===0&&this.stage===0x4000)port(this.out.readPointer());}});
}
function performance(object){
 hook(method(object,44),{onEnter(args){this.music=args[1];},onLeave(result){if(result.toInt32()===0)music(this.music.readPointer());}});
 hook(method(object,49),{onEnter(args){this.out=args[4];},onLeave(result){if(result.toInt32()===0)path(this.out.readPointer());}});
}
function music(object){
 hook(method(object,7),{onEnter(args){this.out=args[2];},onLeave(result){row('master-clock-result',{result:result.toInt32(),clock:this.out.readPointer().toString()});}});
 hook(method(object,4),{onEnter(args){this.out=args[2];if(!masterClock){const id=Memory.alloc(16),clock=Memory.alloc(Process.pointerSize),get=new NativeFunction(method(args[0],7),'int',['pointer','pointer','pointer'],'stdcall');if(get(args[0],id,clock)===0)masterClock=clock.readPointer();}},onLeave(result){if(result.toInt32()===0)buffer(this.out.readPointer());}});
 hook(method(object,5),{onEnter(args){this.out=args[3];},onLeave(result){if(result.toInt32()===0)port(this.out.readPointer());}});
}
globalThis.observer=Process.attachModuleObserver({onAdded(module){if(module.name.toLowerCase()==='combase.dll'||module.name.toLowerCase()==='ole32.dll')hook(module.findExportByName('CoCreateInstance'),{
 onEnter(args){this.kind=args[0].readU32();this.out=args[4];},
 onLeave(result){if(result.toInt32()===0){if(this.kind===0x636b9f10)music(this.out.readPointer());if(this.kind===0xd2ac2881)performance(this.out.readPointer());}}
});}});
row('armed',{pid:Process.id,pointer_size:Process.pointerSize});send({armed:true});
Process.setExceptionHandler(details=>{row('exception',{type:details.type,address:details.address.toString(),memory:details.memory,backtrace:Thread.backtrace(details.context,Backtracer.ACCURATE).map(DebugSymbol.fromAddress).map(String)});return false;});
// shortcut: keep the extra master-clock reference until diagnostic process exit; release it if the observer becomes reusable.
