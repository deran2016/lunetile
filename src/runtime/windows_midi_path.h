#pragma once
#include <windows.h>
#include <dmusicc.h>
#include <unknwn.h>
#include <shlwapi.h>
#include <wrl/client.h>
#include "midi_audio_config.h"

// Fixed Windows COM ABI calls; the installed Windows SDK omits the Performance declarations.
namespace windows_midi_path {
inline constexpr GUID performance_class={0xd2ac2881,0xb39b,0x11d1,{0x87,0x04,0x00,0x60,0x08,0x93,0xb1,0xbd}};
inline constexpr GUID performance_iid={0x679c4137,0xc62e,0x4147,{0xb2,0xb4,0x9d,0x56,0x9a,0xcb,0x25,0x4c}};
template<class Function> Function method(IUnknown* object,size_t index){return reinterpret_cast<Function>((*reinterpret_cast<void***>(object))[index]);}
inline HRESULT initialize(IUnknown* object,IDirectMusic** music,IDirectSound** sound,HWND window){
    struct AudioParams {DWORD size;BOOL initialize_now;DWORD valid,features,voices,sample_rate;GUID synth;};
    static_assert(sizeof(AudioParams)==40,"Windows MIDI audio-parameter ABI");
    AudioParams params{sizeof(AudioParams),TRUE,5,63,0,44100,{}};
    using Call=HRESULT(STDMETHODCALLTYPE*)(IUnknown*,IDirectMusic**,IDirectSound**,HWND,DWORD,DWORD,DWORD,void*);
    return method<Call>(object,44)(object,music,sound,window,0,16,0,&params);
}
inline HRESULT configuration(IPersistStream** result){
    constexpr GUID configuration_class={0xee0b9ca0,0xa81e,0x11d3,{0x9b,0xd1,0x00,0x80,0xc7,0x15,0x0a,0x74}};
    constexpr GUID loader_class={0xd2ac2892,0xb39b,0x11d1,{0x87,0x04,0x00,0x60,0x08,0x93,0xb1,0xbd}};
    constexpr GUID loader_iid={0x19e7c08c,0x0a44,0x4e6a,{0xa1,0x16,0x59,0x5a,0x7c,0xd5,0xde,0x8c}};
    struct Descriptor {DWORD size,valid;GUID object,kind;FILETIME date;DWORD version_ms,version_ls;WCHAR name[64],category[64],file[MAX_PATH];LONGLONG length;BYTE* bytes;IStream* stream;};
    static_assert(sizeof(Descriptor)==848,"Windows x86 music descriptor ABI");
    Microsoft::WRL::ComPtr<IUnknown> loader;
    HRESULT hr=CoCreateInstance(loader_class,nullptr,CLSCTX_INPROC_SERVER,loader_iid,reinterpret_cast<void**>(loader.GetAddressOf()));if(FAILED(hr))return hr;
    using Cache=HRESULT(STDMETHODCALLTYPE*)(IUnknown*,REFGUID,BOOL);
    hr=method<Cache>(loader.Get(),10)(loader.Get(),configuration_class,FALSE);if(FAILED(hr))return hr;
    auto bytes=midi_audio_config::make();Descriptor desc{};desc.size=sizeof(desc);desc.valid=0x402;desc.kind=configuration_class;desc.length=bytes.size();desc.bytes=bytes.data();
    using Get=HRESULT(STDMETHODCALLTYPE*)(IUnknown*,void*,REFIID,void**);
    return method<Get>(loader.Get(),3)(loader.Get(),&desc,IID_IPersistStream,reinterpret_cast<void**>(result));
}
inline HRESULT create(IUnknown* object,IUnknown** path){
    Microsoft::WRL::ComPtr<IPersistStream> source;
    HRESULT result=configuration(&source);if(FAILED(result))return result;
    using Call=HRESULT(STDMETHODCALLTYPE*)(IUnknown*,IUnknown*,BOOL,IUnknown**);
    return method<Call>(object,48)(object,source.Get(),TRUE,path);
}
inline HRESULT get(IUnknown* object,DWORD channel,DWORD stage,REFIID iid,void** result,DWORD buffer=0){
    using Call=HRESULT(STDMETHODCALLTYPE*)(IUnknown*,DWORD,DWORD,DWORD,REFGUID,DWORD,REFIID,void**);
    return method<Call>(object,3)(object,channel,stage,buffer,GUID_All_Objects,0,iid,result);
}
inline HRESULT volume(IUnknown* object,LONG attenuation){
    using Call=HRESULT(STDMETHODCALLTYPE*)(IUnknown*,LONG,DWORD);
    return method<Call>(object,5)(object,attenuation,0);
}
inline HRESULT close(IUnknown* object){
    using Call=HRESULT(STDMETHODCALLTYPE*)(IUnknown*);
    return method<Call>(object,38)(object);
}
}
