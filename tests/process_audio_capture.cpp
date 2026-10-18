// Diagnostic only: WASAPI loopback is restricted to the explicitly launched test process tree.
#include <windows.h>
#include <audioclient.h>
#include <mmdeviceapi.h>
#include <audioclientactivationparams.h>
#include <wrl.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <vector>
using Microsoft::WRL::ComPtr;
static void check(HRESULT hr,const char* operation) {
 if(FAILED(hr)){char message[192];sprintf_s(message,"%s failed: 0x%08lx",operation,static_cast<unsigned long>(hr));throw std::runtime_error(message);}
}
struct Handle {
 HANDLE value=nullptr;
 explicit Handle(HANDLE v):value(v){if(!v || v==INVALID_HANDLE_VALUE)throw std::runtime_error("Handle creation failed");}
 ~Handle(){CloseHandle(value);}
};
class Activation final:public Microsoft::WRL::RuntimeClass<Microsoft::WRL::RuntimeClassFlags<Microsoft::WRL::ClassicCom>,Microsoft::WRL::FtmBase,IActivateAudioInterfaceCompletionHandler> {
public:
 Handle completed{CreateEventW(nullptr,FALSE,FALSE,nullptr)};
 HRESULT result=E_PENDING;
 ComPtr<IAudioClient> client;
 STDMETHODIMP ActivateCompleted(IActivateAudioInterfaceAsyncOperation* operation) override {
  ComPtr<IUnknown> object;HRESULT activated=E_FAIL;
  result=operation->GetActivateResult(&activated,&object);
  if(SUCCEEDED(result))result=activated;
  if(SUCCEEDED(result))result=object.As(&client);
  SetEvent(completed.value);return S_OK;
 }
};
static void write_all(HANDLE file,const void* data,DWORD size){DWORD written=0;if(!WriteFile(file,data,size,&written,nullptr)||written!=size)throw std::runtime_error("Capture write failed");}
int wmain(int argc,wchar_t** argv){
 try {
  if(argc!=5)throw std::runtime_error("Usage: process_audio_capture PID SECONDS OUTPUT.wav READY_FILE");
  wchar_t *end=nullptr;unsigned long pid=wcstoul(argv[1],&end,10);
  if(!pid||*end)throw std::runtime_error("Invalid PID");
  unsigned long seconds=wcstoul(argv[2],&end,10);
  if(!seconds||seconds>120||*end)throw std::runtime_error("Capture must be 1..120 seconds");
  Handle target(OpenProcess(SYNCHRONIZE|PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid));
  check(CoInitializeEx(nullptr,COINIT_MULTITHREADED),"CoInitializeEx");
  auto activation=Microsoft::WRL::Make<Activation>();
  AUDIOCLIENT_ACTIVATION_PARAMS params={};params.ActivationType=AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK;
  params.ProcessLoopbackParams.TargetProcessId=pid;
  params.ProcessLoopbackParams.ProcessLoopbackMode=PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE;
  PROPVARIANT property={};property.vt=VT_BLOB;property.blob.cbSize=sizeof(params);property.blob.pBlobData=reinterpret_cast<BYTE*>(&params);
  ComPtr<IActivateAudioInterfaceAsyncOperation> operation;
  check(ActivateAudioInterfaceAsync(VIRTUAL_AUDIO_DEVICE_PROCESS_LOOPBACK,__uuidof(IAudioClient),&property,activation.Get(),&operation),"ActivateAudioInterfaceAsync");
  if(WaitForSingleObject(activation->completed.value,10000)!=WAIT_OBJECT_0)throw std::runtime_error("Audio activation timed out");
  check(activation->result,"Process audio activation");
  WAVEFORMATEX format={WAVE_FORMAT_PCM,2,44100,176400,4,16,0};
  auto client=activation->client;
  check(client->Initialize(AUDCLNT_SHAREMODE_SHARED,AUDCLNT_STREAMFLAGS_LOOPBACK|AUDCLNT_STREAMFLAGS_EVENTCALLBACK|AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM,0,0,&format,nullptr),"Audio Initialize");
  Handle available(CreateEventW(nullptr,FALSE,FALSE,nullptr));
  check(client->SetEventHandle(available.value),"SetEventHandle");
  ComPtr<IAudioCaptureClient> capture;check(client->GetService(IID_PPV_ARGS(&capture)),"Capture service");
  Handle file(CreateFileW(argv[3],GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr));
  uint32_t header[]={0x46464952,36,0x45564157,0x20746d66,16,0x00020001,44100,176400,0x00100004,0x61746164,0};
  write_all(file.value,header,sizeof(header));
  check(client->Start(),"Capture Start");
  FILETIME epoch={};LARGE_INTEGER counter={},frequency={};
  GetSystemTimePreciseAsFileTime(&epoch);QueryPerformanceCounter(&counter);QueryPerformanceFrequency(&frequency);
  ULARGE_INTEGER stamp={};stamp.LowPart=epoch.dwLowDateTime;stamp.HighPart=epoch.dwHighDateTime;
  const double epoch_seconds=stamp.QuadPart/10000000.0-11644473600.0;
  double first_packet_epoch=0;
  {Handle ready(CreateFileW(argv[4],GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr));write_all(ready.value,"ready",5);}
  auto started=GetTickCount64();uint32_t bytes=0,packets=0,discontinuities=0,timestamp_errors=0,silent=0;bool target_exited=false;
  std::vector<BYTE> zeros;
  while(GetTickCount64()-started<seconds*1000ULL){
   DWORD wait=WaitForSingleObject(available.value,200);
   if(wait!=WAIT_OBJECT_0 && wait!=WAIT_TIMEOUT)throw std::runtime_error("Capture event wait failed");
   UINT32 frames=0;check(capture->GetNextPacketSize(&frames),"GetNextPacketSize");
   while(frames){
    BYTE* data=nullptr;DWORD flags=0;UINT64 position=0,qpc=0;
    check(capture->GetBuffer(&data,&frames,&flags,&position,&qpc),"GetBuffer");
    if(!packets)first_packet_epoch=epoch_seconds+qpc/10000000.0-static_cast<double>(counter.QuadPart)/frequency.QuadPart;
    DWORD length=frames*format.nBlockAlign;
    if(flags&AUDCLNT_BUFFERFLAGS_SILENT){zeros.assign(length,0);data=zeros.data();++silent;}
    if(flags&AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY)++discontinuities;
    if(flags&AUDCLNT_BUFFERFLAGS_TIMESTAMP_ERROR)++timestamp_errors;
    write_all(file.value,data,length);bytes+=length;++packets;
    check(capture->ReleaseBuffer(frames),"ReleaseBuffer");
    check(capture->GetNextPacketSize(&frames),"GetNextPacketSize");
   }
   if(WaitForSingleObject(target.value,0)==WAIT_OBJECT_0){target_exited=true;break;}
  }
  check(client->Stop(),"Capture Stop");
  header[1]=36+bytes;header[10]=bytes;LARGE_INTEGER zero={};
  if(!SetFilePointerEx(file.value,zero,nullptr,FILE_BEGIN))throw std::runtime_error("WAV seek failed");
  write_all(file.value,header,sizeof(header));
  if(!FlushFileBuffers(file.value))throw std::runtime_error("Capture flush failed");
  printf("{\"pid\":%lu,\"bytes\":%u,\"packets\":%u,\"silent_packets\":%u,\"discontinuities\":%u,\"timestamp_errors\":%u,\"target_exited\":%s,\"first_packet_epoch_seconds\":%.9f,\"scope\":\"Target process tree only; not physical speaker latency\"}\n",pid,bytes,packets,silent,discontinuities,timestamp_errors,target_exited?"true":"false",first_packet_epoch);
  return bytes?0:2;
 }catch(const std::exception& error){fprintf(stderr,"%s\n",error.what());return 1;}
}
