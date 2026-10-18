#include <windows.h>
#include <xaudio2.h>
#include <mmsystem.h>
#include <dmusicc.h>
#include <strmif.h>
#include <shlwapi.h>
#include <wrl/client.h>
#include <mfapi.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <deque>
#include <functional>
#include <future>
#include <memory>
#include <map>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include <ruby.h>
#include "audio.h"
#include "windows_midi_path.h"

namespace {
using Clock=std::chrono::steady_clock;
void checked(HRESULT hr,const char* action){if(FAILED(hr))throw std::runtime_error(std::string(action)+" (HRESULT "+std::to_string(static_cast<unsigned long>(hr))+")");}
using Microsoft::WRL::ComPtr;
struct MidiOutput {
    struct Window {HWND handle=nullptr;~Window(){if(handle)DestroyWindow(handle);}} window;
    struct Performance {ComPtr<IUnknown> value;~Performance(){if(value)windows_midi_path::close(value.Get());}} performance;
    ComPtr<IUnknown> path;
    ComPtr<IDirectSound8> sound;
    ComPtr<IDirectMusic8> music;
    ComPtr<IDirectMusicPort> port;
    ComPtr<IDirectSoundBuffer> buffer;
    ComPtr<IDirectMusicCollection> collection;
    ComPtr<IDirectMusicBuffer> messages;
    ComPtr<IReferenceClock> clock,master;
    std::map<DWORD,ComPtr<IDirectMusicDownloadedInstrument>> instruments;
    std::array<unsigned,16> bank_msb{},bank_lsb{};
    explicit MidiOutput(float playback_rate){
        window.handle=CreateWindowExW(0,L"STATIC",L"RGSSXP MIDI",WS_POPUP,0,0,1,1,nullptr,nullptr,GetModuleHandleW(nullptr),nullptr);
        if(!window.handle)throw std::runtime_error("MIDI output window creation failed");
        checked(CoCreateInstance(windows_midi_path::performance_class,nullptr,CLSCTX_INPROC_SERVER,windows_midi_path::performance_iid,reinterpret_cast<void**>(performance.value.GetAddressOf())),"Windows MIDI output manager");
        ComPtr<IDirectMusic> basic_music;ComPtr<IDirectSound> basic_sound;
        checked(windows_midi_path::initialize(performance.value.Get(),&basic_music,&basic_sound,window.handle),"Initialize Windows MIDI output");
        checked(basic_music->QueryInterface(IID_IDirectMusic8,reinterpret_cast<void**>(music.GetAddressOf())),"Windows MIDI core interface");
        checked(basic_sound->QueryInterface(IID_IDirectSound8,reinterpret_cast<void**>(sound.GetAddressOf())),"Windows MIDI sound device");
        checked(windows_midi_path::create(performance.value.Get(),&path),"Independent Windows MIDI audio path");
        checked(windows_midi_path::get(path.Get(),0,0x4000,IID_IDirectMusicPort,reinterpret_cast<void**>(port.GetAddressOf())),"Windows MIDI audio-path port");
        checked(windows_midi_path::get(path.Get(),0xfffffffb,0x6000,IID_IDirectSoundBuffer,reinterpret_cast<void**>(buffer.GetAddressOf()),1),"Windows MIDI dry output buffer");
        DWORD size=0;checked(buffer->GetFormat(nullptr,0,&size),"MIDI format dimensions");
        if(size<sizeof(WAVEFORMATEX)||size>4096)throw std::runtime_error("Invalid MIDI output dimensions");
        std::vector<unsigned char> format(size);checked(buffer->GetFormat(reinterpret_cast<WAVEFORMATEX*>(format.data()),size,nullptr),"MIDI output format");
        auto* wave=reinterpret_cast<WAVEFORMATEX*>(format.data());
        if(wave->nSamplesPerSec!=44100||wave->nChannels!=2||wave->wBitsPerSample!=16)throw std::runtime_error("Unsupported Windows MIDI PCM format: "+std::to_string(wave->nSamplesPerSec)+"Hz/"+std::to_string(wave->nChannels)+" channels/"+std::to_string(wave->wBitsPerSample)+" bits");
        wchar_t system[MAX_PATH]{};UINT length=GetSystemDirectoryW(system,MAX_PATH);if(!length||length>=MAX_PATH)throw std::runtime_error("Windows MIDI bank directory unavailable");
        std::wstring bank=std::wstring(system)+L"\\drivers\\gm.dls";
        ComPtr<IStream> file;checked(SHCreateStreamOnFileEx(bank.c_str(),STGM_READ|STGM_SHARE_DENY_WRITE,0,FALSE,nullptr,&file),"Windows GM bank");
        checked(CoCreateInstance(CLSID_DirectMusicCollection,nullptr,CLSCTX_INPROC_SERVER,IID_IDirectMusicCollection,reinterpret_cast<void**>(collection.GetAddressOf())),"MIDI instrument collection");
        ComPtr<IPersistStream> persist;checked(collection.As(&persist),"MIDI bank persistence");checked(persist->Load(file.Get()),"Load Windows GM bank");
        download(0);download(0x80000000u);
        DMUS_BUFFERDESC message_desc{};message_desc.dwSize=sizeof(message_desc);message_desc.cbBuffer=131072;
        checked(music->CreateMusicBuffer(&message_desc,&messages,nullptr),"MIDI message buffer");
        pitch(playback_rate);
        checked(port->GetLatencyClock(&clock),"MIDI latency clock");checked(port->Activate(TRUE),"MIDI port activation");
        // The initial clock aliases master time until the synth renders its first output buffer.
        GUID master_id{};
        checked(music->GetMasterClock(&master_id,&master),"MIDI master clock");
        if(!master)throw std::runtime_error("MIDI master clock unavailable");
        auto deadline=Clock::now()+std::chrono::seconds(1);
        for(;;){
            REFERENCE_TIME current=0,writable=0;
            checked(master->GetTime(&current),"MIDI current time");checked(clock->GetTime(&writable),"MIDI ready time");
            if(writable-current>10000)break;
            if(Clock::now()>=deadline)throw std::runtime_error("MIDI output clock did not become ready");
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    }
    ~MidiOutput(){if(port){port->Activate(FALSE);for(auto& item:instruments)port->UnloadInstrument(item.second.Get());}}
    void download(DWORD patch){if(instruments.count(patch))return;ComPtr<IDirectMusicInstrument> instrument;checked(collection->GetInstrument(patch,&instrument),"MIDI bank/program instrument");ComPtr<IDirectMusicDownloadedInstrument> downloaded;checked(port->DownloadInstrument(instrument.Get(),&downloaded,nullptr,0),"MIDI instrument download");instruments.emplace(patch,std::move(downloaded));}
    REFERENCE_TIME message_time(){checked(messages->Flush(),"Clear MIDI message buffer");REFERENCE_TIME now=0;checked(clock->GetTime(&now),"MIDI writable time");checked(messages->SetStartTime(now),"MIDI message start");return now;}
    double queued_microseconds(){REFERENCE_TIME now=0,writable=0;checked(master->GetTime(&now),"MIDI current time");checked(clock->GetTime(&writable),"MIDI writable time");return std::max(0.0,(writable-now)/10.0);}
    void short_message(unsigned channel,DWORD message){
        unsigned status=message&0xf0,first=(message>>8)&127,second=(message>>16)&127;
        if(status==0xb0&&first==0)bank_msb[channel]=second;
        if(status==0xb0&&first==32)bank_lsb[channel]=second;
        if(status==0xc0)download(first|(bank_lsb[channel]<<8)|(bank_msb[channel]<<16)|(channel==9?0x80000000u:0));
        checked(messages->PackStructured(message_time(),1,(message&~15u)|channel),"MIDI channel event");checked(port->PlayBuffer(messages.Get()),"MIDI channel submission");
    }
    void release(){for(unsigned i=0;i<16;++i){short_message(i,0xb0|(120<<8));short_message(i,0xb0|(121<<8));}bank_msb={};bank_lsb={};}
    void sysex(const std::vector<unsigned char>& bytes){
        checked(messages->PackUnstructured(message_time(),1,static_cast<DWORD>(bytes.size()),const_cast<BYTE*>(bytes.data())),"MIDI SysEx event");checked(port->PlayBuffer(messages.Get()),"MIDI SysEx submission");
    }
    void gain(float value){LONG db=value<=0?DSBVOLUME_MIN:static_cast<LONG>(std::lround((value-1)*3500));checked(windows_midi_path::volume(path.Get(),db),"MIDI audio-path volume");}
    void pitch(float value){checked(buffer->SetFrequency(static_cast<DWORD>(std::lround(44100*value))),"MIDI PCM resampling");}
    DWORD frequency(){DWORD value=0;checked(buffer->GetFrequency(&value),"MIDI PCM frequency query");return value;}
};
struct MidiChannel {
    std::array<unsigned char,128> control{},velocity{};
    std::array<bool,128> seen{},held{};
    unsigned program=0,bend=8192,pressure=0;
    bool used=false;
    MidiChannel(){control[7]=100;control[10]=64;control[11]=127;}
};
struct Voice {
    AudioData data;
    std::string key;
    IXAudio2SourceVoice* pcm=nullptr;
    std::shared_ptr<MidiOutput> midi;
    std::array<MidiChannel,16> midi_channels;
    size_t event=0;
    Clock::time_point began{},fade_began{},fade_end{},resume_began{},next_gain{};
    double elapsed_us=0,completion_us=0;
    float volume=1,pitch=1,fade_start=1;
    bool loop=false,paused=false,fading=false,ended=false,resuming=false;
    ~Voice(){
        if(pcm)pcm->DestroyVoice();
    }
    void restore(unsigned channel,unsigned physical){
        auto& state=midi_channels[channel];
        midi->short_message(physical,0xb0|(0<<8)|(state.control[0]<<16));midi->short_message(physical,0xb0|(32<<8)|(state.control[32]<<16));midi->short_message(physical,0xc0|(state.program<<8));
        // AudioPath controls channel volume; do not overwrite it with the GM default at each loop.
        for(unsigned i=1;i<120;++i)if(i!=32&&(state.seen[i]||i==10||i==11))midi->short_message(physical,0xb0|(i<<8)|(state.control[i]<<16));
        midi->short_message(physical,0xe0|((state.bend&127)<<8)|((state.bend>>7)<<16));midi->short_message(physical,0xd0|(state.pressure<<8));
        for(unsigned note=0;note<128;++note)if(state.velocity[note]){midi->short_message(physical,0x90|(note<<8)|(state.velocity[note]<<16));if(!state.held[note])midi->short_message(physical,0x80|(note<<8));}
    }
    void midi_event(DWORD message){
        unsigned channel=message&15,status=message&0xf0,first=(message>>8)&127,second=(message>>16)&127;auto& state=midi_channels[channel];
        if(!state.used)restore(channel,channel);
        state.used=true;
        if(status==0x90&&second){state.velocity[first]=static_cast<unsigned char>(second);state.held[first]=true;}
        if(status==0x80||(status==0x90&&!second)){state.held[first]=false;if(state.control[64]<64)state.velocity[first]=0;}
        if(status==0xc0)state.program=first;
        if(status==0xd0)state.pressure=first;
        if(status==0xe0)state.bend=first|(second<<7);
        if(status==0xb0){
            state.control[first]=static_cast<unsigned char>(second);state.seen[first]=true;
            if(first==64&&second<64)for(unsigned i=0;i<128;++i)if(!state.held[i])state.velocity[i]=0;
            if(first==120||first==123){state.velocity.fill(0);state.held.fill(false);}
            if(first==121){auto notes=state.velocity;auto held=state.held;unsigned program=state.program;state=MidiChannel{};state.used=true;state.program=program;state.velocity=notes;state.held=held;}
        }
        midi->short_message(channel,message);
    }
    void gain(float value){
        volume=value;
        float amplitude=value<=0?0.0f:std::pow(10.0f,(value-1.0f)*1.75f);
        if(pcm)checked(pcm->SetVolume(amplitude),"XAudio2 volume");
        if(midi){if(resuming){auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now()-resume_began).count();int percent=static_cast<int>(std::min<int64_t>(100,elapsed/10));value=static_cast<int>(std::lround(value*100))*percent/100/100.0f;}midi->gain(paused?0:value);}
        next_gain=Clock::now()+std::chrono::milliseconds(60);
    }
    void pause(bool value,Clock::time_point now){
        if(paused==value)return;
        if(pcm){if(value)checked(pcm->Stop(),"XAudio2 pause");else checked(pcm->Start(),"XAudio2 resume");}
        if(midi){if(value){resuming=false;elapsed_us+=std::chrono::duration<double,std::micro>(now-began).count();midi->gain(0);midi->release();
            // RGSS1 resumes future MIDI events after ME, without retriggering interrupted notes.
            for(auto& state:midi_channels){state.velocity.fill(0);state.held.fill(false);}
        }else{began=now;resume_began=now;resuming=true;midi->gain(0);for(unsigned channel=0;channel<16;++channel)if(midi_channels[channel].used)restore(channel,channel);}}
        paused=value;
    }
    void update(Clock::time_point now){
        if(fading){
            auto length=std::chrono::duration_cast<std::chrono::milliseconds>(fade_end-fade_began).count();
            auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(now-fade_began).count();
            if(elapsed>=length){ended=true;return;}
            int remaining=100-static_cast<int>(elapsed*100/length);
            int effective=static_cast<int>(std::lround(fade_start*100))*remaining/100;
            gain(effective/100.0f);
        }
        if(midi&&now>=next_gain)gain(volume);
        if(paused)return;
        if(resuming){gain(volume);if(now-resume_began>=std::chrono::seconds(1))resuming=false;}
        if(pcm){XAUDIO2_VOICE_STATE state{};pcm->GetState(&state,XAUDIO2_VOICE_NOSAMPLESPLAYED);if(!state.BuffersQueued)ended=true;return;}
        if(!midi)return;
        // shortcut: preserve SMF wall timing; compare original MIDI waveform/envelopes before claiming timing parity at other pitches.
        double time=elapsed_us+std::chrono::duration<double,std::micro>(now-began).count();
        while(event<data.midi.size()&&data.midi[event].microseconds<=time){
            const auto& item=data.midi[event++];
            if(!item.sysex.empty())midi->sysex(item.sysex);else midi_event(item.message);
        }
        if(time>=(loop?data.duration_us:completion_us)){if(loop){midi->release();event=0;elapsed_us=0;began=now;midi_channels={};}else ended=true;}
    }
};
struct Snapshot {unsigned kind=0,queued=0,channels=0,rate=0,output_frequency=0;uint64_t samples=0,duration=0;float volume=0,pitch=0,linear_gain=-1;bool midi=false,paused=false,fading=false;std::string decoder;};
class AudioWorker {
    std::mutex mutex;
    std::condition_variable ready;
    std::deque<std::function<void()>> jobs;
    std::thread thread;
    bool closing=false;
    IXAudio2* engine=nullptr;
    IXAudio2MasteringVoice* master=nullptr;
    std::array<std::unique_ptr<Voice>,3> channels;
    std::array<std::shared_ptr<MidiOutput>,3> midi_outputs;
    std::vector<std::unique_ptr<Voice>> effects;
    std::string asynchronous_error;
    HRESULT com=E_FAIL,mf=E_FAIL;
    void finish(std::unique_ptr<Voice>& voice){
        if(voice&&voice->midi){voice->midi->gain(0);voice->midi->release();voice->midi->gain(1);}
        voice.reset();
    }
    void initialize(){if(master)return;checked(com,"Audio COM initialization");checked(XAudio2Create(&engine,0,XAUDIO2_DEFAULT_PROCESSOR),"XAudio2 initialization");HRESULT result=engine->CreateMasteringVoice(&master);if(FAILED(result)){engine->Release();engine=nullptr;checked(result,"XAudio2 output device");}}
    void step(){
        auto now=Clock::now();
        for(auto& voice:channels)if(voice){voice->update(now);if(voice->ended)finish(voice);}
        if(channels[0])channels[0]->pause(channels[2]!=nullptr,now);
        for(auto it=effects.begin();it!=effects.end();){(*it)->update(now);if((*it)->ended){finish(*it);it=effects.erase(it);}else ++it;}
    }
    void loop(){
        com=CoInitializeEx(nullptr,COINIT_MULTITHREADED);if(SUCCEEDED(com))mf=MFStartup(MF_VERSION,MFSTARTUP_FULL);
        for(;;){std::function<void()> job;
            {std::unique_lock<std::mutex> lock(mutex);ready.wait_for(lock,std::chrono::milliseconds(5),[&]{return closing||!jobs.empty();});if(closing&&jobs.empty())break;if(!jobs.empty()){job=std::move(jobs.front());jobs.pop_front();}}
            if(job)job();
            try{step();}catch(const std::exception& e){asynchronous_error=e.what();for(auto& voice:channels)voice.reset();effects.clear();for(auto& output:midi_outputs)output.reset();}
        }
        for(auto& voice:channels)voice.reset();effects.clear();for(auto& output:midi_outputs)output.reset();if(master)master->DestroyVoice();if(engine)engine->Release();if(SUCCEEDED(mf))MFShutdown();if(SUCCEEDED(com))CoUninitialize();
    }
    void prior_error(){if(!asynchronous_error.empty()){auto message=std::move(asynchronous_error);asynchronous_error.clear();throw std::runtime_error(message);}}
public:
    AudioWorker(){thread=std::thread([this]{loop();});}
    ~AudioWorker(){{std::lock_guard<std::mutex> lock(mutex);closing=true;}ready.notify_one();thread.join();}
    template<class Work> auto invoke(Work action)->decltype(action()){
        auto task=std::make_shared<std::packaged_task<decltype(action())()>>(std::move(action));auto future=task->get_future();
        {std::lock_guard<std::mutex> lock(mutex);jobs.emplace_back([task]{(*task)();});}ready.notify_one();return future.get();
    }
    void play(unsigned kind,std::string key,std::vector<unsigned char> bytes,int volume,int pitch){
        prior_error();step();auto now=Clock::now();
        if(kind<2&&channels[kind]&&channels[kind]->key==key&&channels[kind]->pitch==pitch/100.0f&&!channels[kind]->fading){auto& voice=*channels[kind];voice.gain(volume/100.0f);return;}
        if(kind==3&&effects.size()>=64)throw std::runtime_error("SE exceeds the 64 simultaneous voice limit");
        auto voice=std::make_unique<Voice>();voice->data=decode_audio(bytes);voice->key=std::move(key);voice->loop=kind<2;voice->pitch=pitch/100.0f;voice->began=now;
        size_t total=voice->data.pcm.size();for(auto& active:channels)if(active)total+=active->data.pcm.size();for(auto& active:effects)total+=active->data.pcm.size();if(total>256*1024*1024)throw std::runtime_error("Active decoded audio exceeds 256 MiB");
        if(voice->data.is_midi){
            checked(com,"MIDI COM initialization");
            if(kind<3){auto& output=midi_outputs[kind];if(!output)output=std::make_shared<MidiOutput>(voice->pitch);else output->pitch(voice->pitch);finish(channels[kind]);voice->midi=output;}
            else voice->midi=std::make_shared<MidiOutput>(voice->pitch);
            voice->completion_us=voice->data.midi_segment_us+voice->midi->queued_microseconds();voice->paused=kind==0&&channels[2]!=nullptr;voice->gain(volume/100.0f);
        }else{
            initialize();checked(engine->CreateSourceVoice(&voice->pcm,&voice->data.format,0,2.0f),"XAudio2 source voice");
            XAUDIO2_BUFFER buffer{};buffer.Flags=XAUDIO2_END_OF_STREAM;buffer.pAudioData=voice->data.pcm.data();buffer.AudioBytes=static_cast<UINT32>(voice->data.pcm.size());
            if(voice->loop){buffer.LoopCount=XAUDIO2_LOOP_INFINITE;buffer.LoopBegin=voice->data.loop_start;buffer.LoopLength=voice->data.loop_length;}
            // Original WMA output ignores pitch in all four roles; keep the requested value for existing replay policy.
            checked(voice->pcm->SubmitSourceBuffer(&buffer),"XAudio2 audio buffer");voice->gain(volume/100.0f);checked(voice->pcm->SetFrequencyRatio(voice->data.ignore_pitch?1.0f:voice->pitch),"XAudio2 pitch");
            if(kind==0&&channels[2])voice->paused=true;else checked(voice->pcm->Start(),"XAudio2 playback");
        }
        voice->began=Clock::now();if(kind==3)effects.push_back(std::move(voice));else{finish(channels[kind]);channels[kind]=std::move(voice);if(kind==2&&channels[0])channels[0]->pause(true,Clock::now());}
    }
    void stop(unsigned kind){prior_error();if(kind==3){for(auto it=effects.begin();it!=effects.end();){finish(*it);it=effects.erase(it);}}else finish(channels[kind]);step();}
    void fade(unsigned kind,int milliseconds){prior_error();step();if(!milliseconds){stop(kind);return;}if(channels[kind]){auto& voice=*channels[kind];voice.fading=true;voice.fade_start=voice.volume;voice.fade_began=Clock::now();voice.fade_end=voice.fade_began+std::chrono::milliseconds(milliseconds);}}
    std::vector<Snapshot> snapshot(){prior_error();step();std::vector<Snapshot> result;
        auto add=[&](Voice& voice,unsigned kind){Snapshot item;item.kind=kind;item.midi=voice.data.is_midi;item.paused=voice.paused;item.fading=voice.fading;item.volume=voice.volume;item.pitch=voice.pitch;item.duration=voice.data.duration_us;item.decoder=voice.data.decoder;item.channels=voice.data.format.nChannels;item.rate=voice.data.format.nSamplesPerSec;if(voice.pcm){XAUDIO2_VOICE_STATE state{};voice.pcm->GetState(&state);voice.pcm->GetVolume(&item.linear_gain);item.samples=state.SamplesPlayed;item.queued=state.BuffersQueued;}else{item.samples=voice.event;item.queued=voice.ended?0:1;item.output_frequency=voice.midi->frequency();item.channels=2;item.rate=44100;}result.push_back(std::move(item));};
        for(unsigned i=0;i<3;++i)if(channels[i])add(*channels[i],i);for(auto& voice:effects)add(*voice,3);return result;
    }
};
std::unique_ptr<AudioWorker> worker;
AudioWorker& audio(){if(!worker)worker=std::make_unique<AudioWorker>();return *worker;}
VALUE play(VALUE,VALUE vk,VALUE key,VALUE bytes,VALUE vv,VALUE vp){
    unsigned kind=NUM2UINT(vk);if(kind>3)rb_raise(rb_eArgError,"Invalid audio channel");StringValue(key);StringValue(bytes);int volume=NUM2INT(vv),pitch=NUM2INT(vp);
    if(volume<0||volume>100||pitch<50||pitch>150||RSTRING_LEN(bytes)>128*1024*1024)rb_raise(rb_eArgError,"Audio volume/pitch/data exceeds supported limits");
    char failure[512]{};{try{std::string name(RSTRING_PTR(key),RSTRING_LEN(key));std::vector<unsigned char> copied(RSTRING_PTR(bytes),RSTRING_PTR(bytes)+RSTRING_LEN(bytes));auto& target=audio();target.invoke([&target,kind,name=std::move(name),copied=std::move(copied),volume,pitch]()mutable{target.play(kind,std::move(name),std::move(copied),volume,pitch);});}catch(const std::exception& e){strncpy_s(failure,e.what(),_TRUNCATE);}}
    RB_GC_GUARD(key);RB_GC_GUARD(bytes);if(*failure)rb_raise(rb_path2class("RGSSError"),"Audio: %s",failure);return Qnil;
}
VALUE stop(VALUE,VALUE value){unsigned kind=NUM2UINT(value);if(kind>3)rb_raise(rb_eArgError,"Invalid audio channel");char failure[512]{};{try{auto& target=audio();target.invoke([&target,kind]{target.stop(kind);});}catch(const std::exception& e){strncpy_s(failure,e.what(),_TRUNCATE);}}if(*failure)rb_raise(rb_path2class("RGSSError"),"Audio: %s",failure);return Qnil;}
VALUE fade(VALUE,VALUE vk,VALUE vm){unsigned kind=NUM2UINT(vk);int milliseconds=NUM2INT(vm);if(kind>2||milliseconds<0)rb_raise(rb_eArgError,"Invalid audio fade");char failure[512]{};{try{auto& target=audio();target.invoke([&target,kind,milliseconds]{target.fade(kind,milliseconds);});}catch(const std::exception& e){strncpy_s(failure,e.what(),_TRUNCATE);}}if(*failure)rb_raise(rb_path2class("RGSSError"),"Audio: %s",failure);return Qnil;}
VALUE snapshot(VALUE){
    char failure[512]{};static std::string text;text.clear();
    {try{auto& target=audio();auto records=target.invoke([&target]{return target.snapshot();});for(auto& item:records){text+=std::to_string(item.kind)+","+std::to_string(item.queued)+","+std::to_string(item.samples)+","+std::to_string(item.duration)+","+std::to_string(item.channels)+","+std::to_string(item.rate)+","+std::to_string(item.volume)+","+std::to_string(item.pitch)+","+(item.paused?"1":"0")+","+(item.fading?"1":"0")+","+item.decoder+","+(item.linear_gain>=0?std::to_string(item.linear_gain):"")+","+std::to_string(item.output_frequency)+"\n";}}catch(const std::exception& e){strncpy_s(failure,e.what(),_TRUNCATE);}}
    if(*failure)rb_raise(rb_path2class("RGSSError"),"Audio: %s",failure);return rb_str_new(text.data(),static_cast<long>(text.size()));
}
}
void audio_shutdown(){worker.reset();}
void init_audio(){VALUE module=rb_define_module("Audio");rb_define_singleton_method(module,"__play",RUBY_METHOD_FUNC(play),5);rb_define_singleton_method(module,"__stop",RUBY_METHOD_FUNC(stop),1);rb_define_singleton_method(module,"__fade",RUBY_METHOD_FUNC(fade),2);rb_define_singleton_method(module,"__snapshot",RUBY_METHOD_FUNC(snapshot),0);}
