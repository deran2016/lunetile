#pragma once
#include <windows.h>
#include <mmsystem.h>
#include <dsound.h>
#include <dmusicc.h>
#include <cstring>
#include <vector>
#include <utility>

namespace midi_audio_config {
using Bytes=std::vector<unsigned char>;
inline void append(Bytes& out,const void* value,size_t size){auto* first=static_cast<const unsigned char*>(value);out.insert(out.end(),first,first+size);}
template<class T> void value(Bytes& out,const T& item){append(out,&item,sizeof(item));}
inline void number(Bytes& out,DWORD item){value(out,item);}
inline void tag(Bytes& out,const char* item){append(out,item,4);}
inline void join(Bytes& out,const Bytes& part){out.insert(out.end(),part.begin(),part.end());}
inline Bytes chunk(const char* type,Bytes data){Bytes out;tag(out,type);number(out,static_cast<DWORD>(data.size()));join(out,data);if(data.size()&1)out.push_back(0);return out;}
inline Bytes container(const char* type,const char* form,Bytes data){Bytes body;tag(body,form);join(body,data);return chunk(type,std::move(body));}
inline constexpr GUID dry={0xc05cf920,0xfa04,0x4f98,{0xaa,0x80,0x5a,0xe5,0x1a,0xed,0x1a,0x36}};
inline constexpr GUID wet={0x06b6f174,0xb5f7,0x4be1,{0xaf,0x1c,0x31,0x6b,0x85,0xd3,0x49,0xf3}};
inline constexpr GUID path_id={0x3bb5761b,0xb83a,0x4d38,{0x90,0x60,0x83,0xb6,0x99,0x83,0x4d,0x7b}};
inline Bytes buffer(REFGUID id,bool reverb){
    Bytes attributes;value(attributes,id);number(attributes,0); // Custom buffers, with independent descriptors below.
    Bytes descriptor;number(descriptor,DSBCAPS_CTRLVOLUME|DSBCAPS_CTRLPAN|DSBCAPS_CTRLFX|DSBCAPS_GLOBALFOCUS|DSBCAPS_LOCDEFER|(reverb?0:DSBCAPS_CTRLFREQUENCY));
    number(descriptor,2);number(descriptor,0);number(descriptor,0);number(descriptor,0); // channels + WORD padding, volume, pan, reserved.
    Bytes buses;number(buses,reverb?DSBUSID_REVERB_SEND:DSBUSID_LEFT);if(!reverb)number(buses,DSBUSID_RIGHT);
    Bytes identifier;value(identifier,id);Bytes configuration;join(configuration,chunk("guid",std::move(identifier)));join(configuration,chunk("dsbd",std::move(descriptor)));join(configuration,chunk("bsid",std::move(buses)));
    if(reverb){
        Bytes header;number(header,0);value(header,GUID_DSFX_WAVES_REVERB);value(header,GUID_NULL);value(header,GUID_NULL);number(header,0);
        DSFXWavesReverb parameters{0,0,1000,0.001f};Bytes data;value(data,parameters);
        Bytes effect;join(effect,chunk("fxhr",std::move(header)));join(effect,chunk("data",std::move(data)));
        join(configuration,container("LIST","fxls",container("RIFF","DSFX",std::move(effect))));
    }
    Bytes list;join(list,chunk("ddah",std::move(attributes)));join(list,container("RIFF","DSBC",std::move(configuration)));
    return container("LIST","dbfl",std::move(list));
}
inline Bytes make(){
    static_assert(sizeof(DMUS_PORTPARAMS)==36&&sizeof(DSFXWavesReverb)==16,"Windows MIDI configuration ABI");
    Bytes header;value(header,GUID_NULL);number(header,0);number(header,128);number(header,3); // default port, drums on channel 10.
    DMUS_PORTPARAMS parameters{};parameters.dwSize=sizeof(parameters);
    parameters.dwValidParams=DMUS_PORTPARAMS_VOICES|DMUS_PORTPARAMS_CHANNELGROUPS|DMUS_PORTPARAMS_AUDIOCHANNELS|DMUS_PORTPARAMS_SAMPLERATE|DMUS_PORTPARAMS_EFFECTS|DMUS_PORTPARAMS_FEATURES;
    parameters.dwVoices=64;parameters.dwChannelGroups=8;parameters.dwAudioChannels=1;parameters.dwSampleRate=44100;parameters.dwFeatures=DMUS_PORT_FEATURE_AUDIOPATH|DMUS_PORT_FEATURE_STREAMING;
    Bytes port_parameters;value(port_parameters,parameters);
    Bytes assignment;number(assignment,0);number(assignment,128);number(assignment,2);number(assignment,0);value(assignment,wet);value(assignment,dry);
    Bytes port;join(port,chunk("pcfh",std::move(header)));join(port,chunk("pprh",std::move(port_parameters)));
    join(port,buffer(wet,true));join(port,buffer(dry,false));join(port,container("LIST","pchl",chunk("pchh",std::move(assignment))));
    Bytes identifier;value(identifier,path_id);Bytes path;join(path,chunk("guid",std::move(identifier)));join(path,container("LIST","pcsl",container("LIST","pcfl",std::move(port))));
    return container("RIFF","DMAP",std::move(path));
}
}
