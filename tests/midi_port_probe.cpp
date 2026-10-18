// An isolated Windows API feasibility test, not a second engine or the runtime MIDI backend.
#include <windows.h>
#include <mmsystem.h>
#include <dsound.h>
#include <dmusicc.h>
#include <strmif.h>
#include <shlwapi.h>
#include <wrl/client.h>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

using Microsoft::WRL::ComPtr;
void checked(HRESULT result,const char* action){if(FAILED(result)){char message[180];sprintf_s(message,"%s: HRESULT 0x%08lx",action,result);throw std::runtime_error(message);}}
struct Apartment {Apartment(){checked(CoInitializeEx(nullptr,COINIT_MULTITHREADED),"COM");}~Apartment(){CoUninitialize();}};
struct Port {ComPtr<IDirectMusicPort> value;~Port(){if(value)value->Activate(FALSE);}};
int main(){
    try{
        Apartment apartment;
        HWND window=CreateWindowExW(0,L"STATIC",L"MIDI port probe",WS_OVERLAPPEDWINDOW,0,0,640,480,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
        if(!window)throw std::runtime_error("Probe window creation failed");
        struct Window {HWND value;~Window(){DestroyWindow(value);}} owner{window};
        ComPtr<IDirectSound8> sound;
        checked(DirectSoundCreate8(nullptr,&sound,nullptr),"DirectSound device");
        checked(sound->SetCooperativeLevel(window,DSSCL_NORMAL),"Cooperative level");
        ComPtr<IDirectMusic8> music;
        checked(CoCreateInstance(CLSID_DirectMusic,nullptr,CLSCTX_INPROC_SERVER,IID_IDirectMusic8,reinterpret_cast<void**>(music.GetAddressOf())),"DirectMusic core");
        checked(music->SetDirectSound(sound.Get(),nullptr),"DirectMusic device association");
        GUID selected{};bool found=false;
        for(DWORD index=0;index<128;++index){
            DMUS_PORTCAPS caps{};caps.dwSize=sizeof(caps);HRESULT result=music->EnumPort(index,&caps);
            if(result==S_FALSE)break;checked(result,"Enumerate MIDI ports");
            if((caps.dwFlags&DMUS_PC_SOFTWARESYNTH)&&caps.dwClass==DMUS_PC_OUTPUTCLASS){selected=caps.guidPort;found=true;break;}
        }
        if(!found)throw std::runtime_error("No independent Windows software synthesizer port");
        DMUS_PORTPARAMS params{};params.dwSize=sizeof(params);
        params.dwValidParams=DMUS_PORTPARAMS_CHANNELGROUPS|DMUS_PORTPARAMS_AUDIOCHANNELS|DMUS_PORTPARAMS_SAMPLERATE|DMUS_PORTPARAMS_SHARE;
        params.dwChannelGroups=1;params.dwAudioChannels=2;params.dwSampleRate=44100;params.fShare=FALSE;
        Port port;checked(music->CreatePort(selected,&params,&port.value,nullptr),"Create independent MIDI port");
        DWORD format_size=0,buffer_size=0;
        HRESULT query=port.value->GetFormat(nullptr,&format_size,&buffer_size);
        if(!format_size||format_size>4096||!buffer_size||buffer_size>4*1024*1024)throw std::runtime_error("Unexpected MIDI output format/buffer dimensions");
        std::vector<unsigned char> format(format_size);
        checked(port.value->GetFormat(reinterpret_cast<WAVEFORMATEX*>(format.data()),&format_size,&buffer_size),"MIDI output format");
        auto* wave=reinterpret_cast<WAVEFORMATEX*>(format.data());
        DSBUFFERDESC desc{};desc.dwSize=sizeof(desc);
        desc.dwFlags=DSBCAPS_CTRLVOLUME|DSBCAPS_CTRLFREQUENCY|DSBCAPS_GLOBALFOCUS|DSBCAPS_GETCURRENTPOSITION2;
        desc.dwBufferBytes=buffer_size;desc.lpwfxFormat=wave;
        ComPtr<IDirectSoundBuffer> buffer;
        checked(sound->CreateSoundBuffer(&desc,&buffer,nullptr),"Create owned PCM buffer");
        void *first=nullptr,*second=nullptr;DWORD first_size=0,second_size=0;
        checked(buffer->Lock(0,buffer_size,&first,&first_size,&second,&second_size,0),"Clear owned buffer");
        memset(first,0,first_size);if(second)memset(second,0,second_size);buffer->Unlock(first,first_size,second,second_size);
        HRESULT assigned=port.value->SetDirectSound(sound.Get(),buffer.Get());
        printf("{\"format_query\":%ld,\"sample_rate\":%lu,\"buffer_bytes\":%lu,\"set_owned_buffer\":%ld}\n",query,wave->nSamplesPerSec,buffer_size,assigned);
        checked(assigned,"Assign owned MIDI output buffer");checked(port.value->Activate(TRUE),"Activate MIDI port");
        wchar_t system[MAX_PATH]{};if(!GetSystemDirectoryW(system,MAX_PATH))throw std::runtime_error("Windows system directory");
        std::wstring bank=std::wstring(system)+L"\\drivers\\gm.dls";
        ComPtr<IStream> file;checked(SHCreateStreamOnFileEx(bank.c_str(),STGM_READ|STGM_SHARE_DENY_WRITE,0,FALSE,nullptr,&file),"Open Windows GM bank");
        ComPtr<IDirectMusicCollection> collection;
        checked(CoCreateInstance(CLSID_DirectMusicCollection,nullptr,CLSCTX_INPROC_SERVER,IID_IDirectMusicCollection,reinterpret_cast<void**>(collection.GetAddressOf())),"GM collection");
        ComPtr<IPersistStream> persist;checked(collection.As(&persist),"GM collection persistence");checked(persist->Load(file.Get()),"Load Windows GM bank");
        ComPtr<IDirectMusicInstrument> instrument;checked(collection->GetInstrument(0,&instrument),"GM piano");
        ComPtr<IDirectMusicDownloadedInstrument> downloaded;checked(port.value->DownloadInstrument(instrument.Get(),&downloaded,nullptr,0),"Download GM piano");
        DMUS_BUFFERDESC messages_desc{};messages_desc.dwSize=sizeof(messages_desc);messages_desc.cbBuffer=1024;
        ComPtr<IDirectMusicBuffer> messages;checked(music->CreateMusicBuffer(&messages_desc,&messages,nullptr),"MIDI message buffer");
        ComPtr<IReferenceClock> clock;checked(port.value->GetLatencyClock(&clock),"MIDI latency clock");
        REFERENCE_TIME start=0;checked(clock->GetTime(&start),"MIDI writable time");
        checked(messages->SetStartTime(start),"MIDI message start");
        checked(messages->PackStructured(start,1,0xc0),"MIDI piano program");
        checked(messages->PackStructured(start,1,0x90|(69<<8)|(100<<16)),"MIDI piano note");
        checked(port.value->PlayBuffer(messages.Get()),"Submit MIDI note");
        Sleep(80);DWORD status=0,position=0,write=0;
        checked(buffer->GetStatus(&status),"MIDI output status");checked(buffer->GetCurrentPosition(&position,&write),"MIDI output cursor");
        printf("{\"owned_buffer_playing\":%s,\"cursor\":%lu}\n",(status&DSBSTATUS_PLAYING)?"true":"false",position);
        if(!(status&DSBSTATUS_PLAYING))return 3;
        Sleep(160);
        checked(buffer->Lock(0,buffer_size,&first,&first_size,&second,&second_size,DSBLOCK_ENTIREBUFFER),"Inspect synthesized PCM");
        size_t nonzero=0;for(DWORD i=0;i<first_size;++i)nonzero+=static_cast<unsigned char*>(first)[i]!=0;
        for(DWORD i=0;i<second_size;++i)nonzero+=static_cast<unsigned char*>(second)[i]!=0;
        buffer->Unlock(first,first_size,second,second_size);
        printf("{\"synthesized_nonzero_bytes\":%zu}\n",nonzero);
        if(!nonzero)return 5;
        checked(buffer->SetFrequency(wave->nSamplesPerSec/2),"MIDI output resampling");
        DWORD frequency=0;checked(buffer->GetFrequency(&frequency),"MIDI output frequency");
        printf("{\"frequency\":%lu}\n",frequency);
        checked(port.value->UnloadInstrument(downloaded.Get()),"Unload GM piano");
        return frequency==wave->nSamplesPerSec/2?0:4;
    }catch(const std::exception& error){fprintf(stderr,"%s\n",error.what());return 1;}
}
