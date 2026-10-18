#define UNICODE
#define _UNICODE
#include <windows.h>
#include <evntrace.h>
#include <tdh.h>
#include <cstdio>
#include <string>
#include <vector>
#include <map>
#include <sstream>
#include <set>

struct Schema {std::wstring provider, task, opcode; std::vector<std::wstring> fields; std::vector<USHORT> types; unsigned long long count=0, target=0;};
std::map<std::wstring,Schema> schemas;
std::map<std::wstring,std::pair<ULONG,unsigned long long>> unavailable;
unsigned long long total=0, failures=0;
ULONG target=34112;
bool extract=false;
std::set<unsigned long long> devices,contexts,queues,threads;
std::map<unsigned long long,unsigned long long> samples,threadSamples;
struct Prof {unsigned long long count=0,ticks=0;};
struct ProfStart {unsigned long long qpc,function,accelerated;};
std::map<ULONG,std::vector<ProfStart>> profStarts;
std::map<std::pair<unsigned long long,unsigned long long>,Prof> profilers;
unsigned long long sampleInterval=0,frequency=0,targetGpu=0,propertyFailures=0;
unsigned long long number(PEVENT_RECORD e,const wchar_t* name,bool* ok=nullptr){
 PROPERTY_DATA_DESCRIPTOR p={};p.PropertyName=(ULONGLONG)name;p.ArrayIndex=ULONG_MAX;
 ULONG size=0;unsigned long long result=0;
 ULONG status=TdhGetPropertySize(e,0,nullptr,1,&p,&size);
 if(status==ERROR_SUCCESS && size<=sizeof(result))status=TdhGetProperty(e,0,nullptr,1,&p,size,(PBYTE)&result);else status=ERROR_INVALID_DATA;
 if(ok)*ok=status==ERROR_SUCCESS;return result;
}
std::string narrow(const std::wstring &s) {std::string out; for(auto c:s)out += c<128?(char)c:'?';return out;}
std::wstring value(PTRACE_EVENT_INFO i, ULONG offset) {return offset?(wchar_t*)((BYTE*)i+offset):L"";}
void WINAPI record(PEVENT_RECORD e) {
 ++total;
 auto d=e->EventHeader.ProviderId.Data1;
 if(d!=0x802ec45a && d!=0xce1dbfb4 && d!=0x3d6fa8d1 && d!=0x2cb15d1d) return;
 wchar_t key[150];swprintf_s(key,L"%08lx:%u:%u:%u",d,e->EventHeader.EventDescriptor.Id,e->EventHeader.EventDescriptor.Version,e->EventHeader.EventDescriptor.Opcode);
 auto missing=unavailable.find(key);if(missing!=unavailable.end()){++missing->second.second;++failures;return;}
 auto it=schemas.find(key);
 if(it==schemas.end()) {
  ULONG bytes=0;TdhGetEventInformation(e,0,nullptr,nullptr,&bytes);std::vector<BYTE>b(bytes);
  auto status=bytes?TdhGetEventInformation(e,0,nullptr,(PTRACE_EVENT_INFO)b.data(),&bytes):ERROR_NOT_FOUND;
  if(status!=ERROR_SUCCESS){++failures;unavailable[key]={status,1};return;}
  auto i=(PTRACE_EVENT_INFO)b.data();Schema s;s.provider=value(i,i->ProviderNameOffset);s.task=value(i,i->TaskNameOffset);s.opcode=value(i,i->OpcodeNameOffset);
  for(ULONG p=0;p<i->TopLevelPropertyCount;++p){auto &prop=i->EventPropertyInfoArray[p];s.fields.push_back(value(i,prop.NameOffset));s.types.push_back(prop.nonStructType.InType);}
  it=schemas.emplace(key,s).first;
 }
 ++it->second.count;if(e->EventHeader.ProcessId==target)++it->second.target;
 if(!extract)return;
 auto &s=it->second;auto op=e->EventHeader.EventDescriptor.Opcode;auto id=e->EventHeader.EventDescriptor.Id;
 if(d==0x2cb15d1d){
  if(number(e,L"ProcessId")==target){
   PROPERTY_DATA_DESCRIPTOR p={};p.PropertyName=(ULONGLONG)L"FileName";p.ArrayIndex=ULONG_MAX;ULONG size=0;
   if(TdhGetPropertySize(e,0,nullptr,1,&p,&size)==ERROR_SUCCESS){std::vector<wchar_t> path(size/2+1);if(TdhGetProperty(e,0,nullptr,1,&p,size,(PBYTE)path.data())==ERROR_SUCCESS){std::wstring full(path.data());auto name=full.substr(full.find_last_of(L"\\/")+1);printf("{\"kind\":\"image\",\"base\":%llu,\"size\":%llu,\"name\":\"%s\"}\n",number(e,L"ImageBase"),number(e,L"ImageSize"),narrow(name).c_str());}}
  }return;
 }
 if(d==0x3d6fa8d1){
  if(op>=1 && op<=4){auto pid=number(e,L"ProcessId"),tid=number(e,L"TThreadId");if(pid==target){if(op==1||op==3)threads.insert(tid);else threads.erase(tid);}}
  return;
 }
 if(d==0xce1dbfb4){
  if(op==73){sampleInterval=number(e,L"NewInterval");printf("{\"kind\":\"sample_interval\",\"ticks_100ns\":%llu}\n",sampleInterval);}
  if(op==46){auto tid=number(e,L"ThreadId");if(threads.count(tid)){++samples[number(e,L"InstructionPointer")];++threadSamples[tid];}}
  return;
 }
 if(s.task==L"ExtendedProfiler" && e->EventHeader.ProcessId==target){
  auto tid=e->EventHeader.ThreadId;auto function=number(e,L"Function");auto accelerated=number(e,L"Accelerated");auto &stack=profStarts[tid];
  if(op==1)stack.push_back({(unsigned long long)e->EventHeader.TimeStamp.QuadPart,function,accelerated});
  if(op==2 && !stack.empty()){auto start=stack.back();stack.pop_back();if(start.function==function){auto &p=profilers[{function,accelerated}];++p.count;p.ticks+=e->EventHeader.TimeStamp.QuadPart-start.qpc;}}
  return;
 }
 if(s.task!=L"Device" && s.task!=L"Context" && s.task!=L"HwQueue" && s.task!=L"DmaPacket" && s.task!=L"QueuePacket")return;
 bool owned=false;
 if(s.task==L"Device" && (op==1||op==3) && number(e,L"hProcessId")==target){devices.insert(number(e,L"hDevice"));owned=true;}
 if(s.task==L"Context" && (op==1||op==3) && devices.count(number(e,L"hDevice"))){contexts.insert(number(e,L"hContext"));owned=true;}
 // hHwQueue on lifecycle events is process-local; only the kernel parent is globally attributable.
 if(s.task==L"HwQueue" && (op==1||op==3) && contexts.count(number(e,L"hContext"))){auto q=number(e,L"ParentDxgHwQueue");if(q){contexts.insert(q);queues.insert(q);}owned=true;}
 for(auto &field:s.fields){if(field==L"hContext"||field==L"DxgContext"||field==L"hQueuePacketContext"){if(contexts.count(number(e,field.c_str())))owned=true;}if(field==L"hHwQueue" && queues.count(number(e,field.c_str())))owned=true;}
 if(owned){
  ++targetGpu;printf("{\"kind\":\"gpu\",\"id\":%u,\"version\":%u,\"opcode\":%u,\"qpc\":%lld,\"task\":\"%s\",\"header_target\":%s,\"values\":{",id,e->EventHeader.EventDescriptor.Version,op,e->EventHeader.TimeStamp.QuadPart,narrow(s.task).c_str(),e->EventHeader.ProcessId==target?"true":"false");
  bool first=true;for(size_t p=0;p<s.fields.size();++p){auto type=s.types[p];if(type==1||type==2||type>21)continue;bool ok=false;auto n=number(e,s.fields[p].c_str(),&ok);if(!ok){++propertyFailures;continue;}printf("%s\"%s\":%llu",first?"":",",narrow(s.fields[p]).c_str(),n);first=false;}puts("}}");
 }
}
int wmain(int argc,wchar_t**argv){
 if((argc!=2 && argc!=4) || (argc==4 && std::wstring(argv[2])!=L"--extract" && std::wstring(argv[2])!=L"--inventory")){fwprintf(stderr,L"usage: etw_extract trace.etl [--extract pid | --inventory pid]\n");return 2;}
 extract=argc==4 && std::wstring(argv[2])==L"--extract";
 if(argc>3){wchar_t*end=nullptr;auto pid=wcstoul(argv[3],&end,10);if(!pid||*end){fwprintf(stderr,L"invalid pid\n");return 2;}target=pid;}
 EVENT_TRACE_LOGFILEW log={};log.LogFileName=argv[1];log.ProcessTraceMode=PROCESS_TRACE_MODE_EVENT_RECORD|PROCESS_TRACE_MODE_RAW_TIMESTAMP;log.EventRecordCallback=record;
 TRACEHANDLE h=OpenTraceW(&log);if(h==INVALID_PROCESSTRACE_HANDLE){printf("open_error=%lu\n",GetLastError());return 1;}
 frequency=log.LogfileHeader.PerfFreq.QuadPart;
 if(extract)printf("{\"kind\":\"header\",\"pid\":%lu,\"frequency\":%llu,\"events_lost\":%lu,\"buffers_lost\":%lu}\n",target,frequency,log.LogfileHeader.EventsLost,log.LogfileHeader.BuffersLost);
 else printf("frequency=%lld events_lost=%lu buffers_lost=%lu\n",log.LogfileHeader.PerfFreq.QuadPart,log.LogfileHeader.EventsLost,log.LogfileHeader.BuffersLost);
 ULONG status=ProcessTrace(&h,1,nullptr,nullptr);CloseTrace(h);
 if(extract){for(auto kv:profilers)printf("{\"kind\":\"dxg_cpu_profiler\",\"function\":%llu,\"accelerated\":%llu,\"count\":%llu,\"duration_qpc\":%llu}\n",kv.first.first,kv.first.second,kv.second.count,kv.second.ticks);for(auto kv:samples)printf("{\"kind\":\"cpu_ip_samples\",\"ip\":%llu,\"count\":%llu}\n",kv.first,kv.second);for(auto kv:threadSamples)printf("{\"kind\":\"cpu_thread_samples\",\"tid\":%llu,\"count\":%llu}\n",kv.first,kv.second);for(auto kv:unavailable)printf("{\"kind\":\"unavailable_schema\",\"key\":\"%s\",\"status\":%lu,\"count\":%llu}\n",narrow(kv.first).c_str(),kv.second.first,kv.second.second);printf("{\"kind\":\"summary\",\"status\":%lu,\"events\":%llu,\"schema_failures\":%llu,\"property_failures\":%llu,\"target_gpu_events\":%llu}\n",status,total,failures,propertyFailures,targetGpu);return status?1:0;}
 printf("status=%lu events=%llu schema_failures=%llu\n",status,total,failures);
 for(auto &kv:schemas){auto&s=kv.second;printf("%s count=%llu header_target=%llu %s/%s/%s\n",narrow(kv.first).c_str(),s.count,s.target,narrow(s.provider).c_str(),narrow(s.task).c_str(),narrow(s.opcode).c_str());for(size_t p=0;p<s.fields.size();++p)printf("  %s type=%u\n",narrow(s.fields[p]).c_str(),s.types[p]);}
 return status?1:0;
}
