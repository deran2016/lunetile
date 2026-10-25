#include <windows.h>
#include <dshow.h>
#include <xaudio2.h>
#include <ogg/ogg.h>
#include <theora/theoradec.h>
#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <vector>
#include "audio.h"
#include <wrl/client.h>
#include <ruby.h>
#ifdef read
#undef read
#endif
#include <stdexcept>
#include <string>
#include "movie.h"
#include "browser.h"
#include "graphics.h"

namespace {
using Microsoft::WRL::ComPtr;
HWND owner=nullptr;
void checked(HRESULT result,const char* message){
    if(FAILED(result))throw std::runtime_error(std::string(message)+" (HRESULT "+std::to_string(static_cast<unsigned long>(result))+")");
}
struct Apartment {
    HRESULT result=CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED);
    Apartment(){if(result!=RPC_E_CHANGED_MODE)checked(result,"Initialize movie playback");}
    ~Apartment(){if(SUCCEEDED(result))CoUninitialize();}
};
struct Playback {
    ComPtr<IGraphBuilder> graph;
    ComPtr<IMediaControl> control;
    ComPtr<IVideoWindow> video;
    ComPtr<IMediaEvent> events;
    ~Playback(){if(control)control->Stop();if(video){video->put_Visible(OAFALSE);video->put_Owner(0);}}
};
int messages(){
    MSG message{};
    while(PeekMessageW(&message,nullptr,0,0,PM_REMOVE)){
        if(message.message==WM_QUIT)return 1;
        if(browser_pretranslate(message)||input_pretranslate(message))continue;
        if(message.message==WM_KEYDOWN&&message.wParam==VK_F12)return 2;
        TranslateMessage(&message);DispatchMessageW(&message);
    }
    browser_pump();
    return IsWindow(owner)?0:1;
}
struct OggPages {
    ogg_sync_state sync{};
    explicit OggPages(const std::vector<unsigned char>& bytes){
        ogg_sync_init(&sync);
        char* buffer=ogg_sync_buffer(&sync,static_cast<long>(bytes.size()));
        if(!buffer){ogg_sync_clear(&sync);throw std::runtime_error("Movie allocation failed");}
        memcpy(buffer,bytes.data(),bytes.size());ogg_sync_wrote(&sync,static_cast<long>(bytes.size()));
    }
    ~OggPages(){ogg_sync_clear(&sync);}
    bool next(ogg_page& page){int result=ogg_sync_pageout(&sync,&page);if(result<0)throw std::runtime_error("Corrupt Ogg movie page");if(result==0&&sync.returned<sync.fill)throw std::runtime_error("Truncated Ogg movie page");return result>0;}
};
struct Theora {
    th_info info{};th_comment comment{};th_setup_info* setup=nullptr;th_dec_ctx* decoder=nullptr;
    ogg_stream_state stream{};
    explicit Theora(int serial){th_info_init(&info);th_comment_init(&comment);if(ogg_stream_init(&stream,serial)!=0)throw std::runtime_error("Movie stream initialization failed");}
    ~Theora(){if(decoder)th_decode_free(decoder);if(setup)th_setup_free(setup);th_comment_clear(&comment);th_info_clear(&info);ogg_stream_clear(&stream);}
};
struct MovieSound {
    IXAudio2* engine=nullptr;IXAudio2MasteringVoice* master=nullptr;IXAudio2SourceVoice* voice=nullptr;
    AudioData data;
    ~MovieSound(){if(voice)voice->DestroyVoice();if(master)master->DestroyVoice();if(engine)engine->Release();}
    void start(const std::vector<unsigned char>& bytes){
        if(bytes.empty())return;
        data=decode_audio(bytes);
        checked(XAudio2Create(&engine,0,XAUDIO2_DEFAULT_PROCESSOR),"Movie audio engine");
        checked(engine->CreateMasteringVoice(&master),"Movie audio output");
        checked(engine->CreateSourceVoice(&voice,&data.format),"Movie audio voice");
        XAUDIO2_BUFFER buffer{};buffer.Flags=XAUDIO2_END_OF_STREAM;buffer.AudioBytes=static_cast<UINT32>(data.pcm.size());buffer.pAudioData=data.pcm.data();
        checked(voice->SubmitSourceBuffer(&buffer),"Movie audio data");checked(voice->Start(),"Movie audio start");
    }
};
struct MovieSurface {
    HWND window=CreateWindowExW(0,L"STATIC",L"",WS_CHILD|WS_VISIBLE|WS_CLIPSIBLINGS,0,0,1,1,owner,nullptr,GetModuleHandleW(nullptr),nullptr);
    MovieSurface(){if(!window)throw std::runtime_error("Movie surface creation failed");}
    ~MovieSurface(){if(IsWindow(window))DestroyWindow(window);}
};
void draw_theora(HWND surface,Theora& video,std::vector<unsigned char>& pixels){
    th_ycbcr_buffer image{};if(th_decode_ycbcr_out(video.decoder,image)!=0)throw std::runtime_error("Movie frame decode failed");
    unsigned width=video.info.pic_width,height=video.info.pic_height;
    pixels.resize(static_cast<size_t>(width)*height*4);
    auto byte=[](int value){return static_cast<unsigned char>(std::clamp(value,0,255));};
    for(unsigned y=0;y<height;++y){
        unsigned sy=y+video.info.pic_y,cy=sy*image[1].height/image[0].height;
        for(unsigned x=0;x<width;++x){
            unsigned sx=x+video.info.pic_x,cx=sx*image[1].width/image[0].width;
            int luma=image[0].data[sy*image[0].stride+sx]-16;
            int u=image[1].data[cy*image[1].stride+cx]-128,v=image[2].data[cy*image[2].stride+cx]-128;
            size_t at=(static_cast<size_t>(y)*width+x)*4;
            pixels[at]=byte((298*luma+516*u+128)>>8);pixels[at+1]=byte((298*luma-100*u-208*v+128)>>8);pixels[at+2]=byte((298*luma+409*v+128)>>8);pixels[at+3]=255;
        }
    }
    BITMAPINFO bitmap{};bitmap.bmiHeader.biSize=sizeof(BITMAPINFOHEADER);bitmap.bmiHeader.biWidth=width;bitmap.bmiHeader.biHeight=-static_cast<LONG>(height);bitmap.bmiHeader.biPlanes=1;bitmap.bmiHeader.biBitCount=32;bitmap.bmiHeader.biCompression=BI_RGB;
    RECT client{};GetClientRect(owner,&client);SetWindowPos(surface,HWND_TOP,0,0,client.right,client.bottom,SWP_NOACTIVATE);HDC dc=GetDC(surface);if(!dc)throw std::runtime_error("Movie drawing surface unavailable");
    double scale=std::min(static_cast<double>(client.right)/width,static_cast<double>(client.bottom)/height);
    int w=static_cast<int>(width*scale),h=static_cast<int>(height*scale);
    FillRect(dc,&client,static_cast<HBRUSH>(GetStockObject(BLACK_BRUSH)));
    SetStretchBltMode(dc,COLORONCOLOR);
    int result=StretchDIBits(dc,(client.right-w)/2,(client.bottom-h)/2,w,h,0,0,width,height,pixels.data(),&bitmap,DIB_RGB_COLORS,SRCCOPY);ReleaseDC(surface,dc);
    if(result==GDI_ERROR)throw std::runtime_error("Movie frame presentation failed");
}
int play_ogg(const std::vector<unsigned char>& bytes){
    Apartment apartment;
    int video_serial=0,audio_serial=0;bool found_video=false,found_audio=false;
    std::vector<unsigned char> audio_bytes;
    {OggPages pages(bytes);ogg_page page{};
        while(pages.next(page)){
            if(ogg_page_bos(&page)&&page.body_len>=7){
                if(page.body[0]==0x80&&memcmp(page.body+1,"theora",6)==0){if(found_video)throw std::runtime_error("Multiple Theora streams are unsupported");video_serial=ogg_page_serialno(&page);found_video=true;}
                if(page.body[0]==1&&memcmp(page.body+1,"vorbis",6)==0){if(found_audio)throw std::runtime_error("Multiple Vorbis streams are unsupported");audio_serial=ogg_page_serialno(&page);found_audio=true;}
            }
            if(found_audio&&ogg_page_serialno(&page)==audio_serial){audio_bytes.insert(audio_bytes.end(),page.header,page.header+page.header_len);audio_bytes.insert(audio_bytes.end(),page.body,page.body+page.body_len);}
        }
    }
    if(!found_video)throw std::runtime_error("Ogg movie has no Theora video stream");
    Theora video(video_serial);MovieSound sound;MovieSurface surface;std::vector<unsigned char> pixels;int headers=0;bool started=false,ended=false;
    using Clock=std::chrono::steady_clock;Clock::time_point began{};double last_time=0;uint64_t frames=0;
    OggPages pages(bytes);ogg_page page{};
    while(pages.next(page)){
        if(ogg_page_serialno(&page)!=video_serial)continue;
        if(ogg_stream_pagein(&video.stream,&page)!=0)throw std::runtime_error("Invalid movie video page");
        ogg_packet packet{};int packet_result=0;
        while((packet_result=ogg_stream_packetout(&video.stream,&packet))!=0){
            if(packet_result<0)throw std::runtime_error("Missing movie video packet");
            if(headers<3){
                if(th_decode_headerin(&video.info,&video.comment,&video.setup,&packet)<=0)throw std::runtime_error("Invalid Theora header");
                if(++headers==3){
                    if(!video.info.pic_width||!video.info.pic_height||video.info.frame_width>4096||video.info.frame_height>4096||!video.info.fps_numerator||!video.info.fps_denominator||video.info.pic_x>video.info.frame_width||video.info.pic_y>video.info.frame_height||video.info.pic_width>video.info.frame_width-video.info.pic_x||video.info.pic_height>video.info.frame_height-video.info.pic_y)throw std::runtime_error("Unsupported movie dimensions or frame rate");
                    video.decoder=th_decode_alloc(&video.info,video.setup);if(!video.decoder)throw std::runtime_error("Theora decoder allocation failed");
                }
                continue;
            }
            ogg_int64_t granule=0;int result=th_decode_packetin(video.decoder,&packet,&granule);
            if(result<0)throw std::runtime_error("Corrupt Theora frame");
            if(!started){sound.start(audio_bytes);began=Clock::now();started=true;}
            double timestamp=frames++*static_cast<double>(video.info.fps_denominator)/video.info.fps_numerator;
            while(std::chrono::duration<double>(Clock::now()-began).count()<timestamp){int action=messages();if(action)return action;MsgWaitForMultipleObjectsEx(0,nullptr,5,QS_ALLINPUT,MWMO_INPUTAVAILABLE);}
            int action=messages();if(action)return action;
            draw_theora(surface.window,video,pixels);last_time=timestamp;
            if(packet.e_o_s)ended=true;
        }
    }
    if(!started||!ended)throw std::runtime_error("Truncated Ogg movie");
    double duration=last_time+static_cast<double>(video.info.fps_denominator)/video.info.fps_numerator;
    while(std::chrono::duration<double>(Clock::now()-began).count()<duration){int action=messages();if(action)return action;MsgWaitForMultipleObjectsEx(0,nullptr,5,QS_ALLINPUT,MWMO_INPUTAVAILABLE);}
    return 0;
}
int run(const std::wstring& path){
    if(!owner||!IsWindow(owner))throw std::runtime_error("Movie playback requires the game window");
    std::ifstream file(std::filesystem::path(path),std::ios::binary|std::ios::ate);
    if(!file)throw std::runtime_error("Movie file not found");
    auto size=file.tellg();if(size<4||size>128*1024*1024)throw std::runtime_error("Movie file is empty or exceeds 128 MiB");
    file.seekg(0);char signature[4]{};file.read(signature,4);
    if(memcmp(signature,"OggS",4)==0){
        std::vector<unsigned char> bytes(static_cast<size_t>(size));file.seekg(0);file.read(reinterpret_cast<char*>(bytes.data()),size);
        if(!file)throw std::runtime_error("Movie file read failed");return play_ogg(bytes);
    }
    Apartment apartment;Playback playback;
    checked(CoCreateInstance(CLSID_FilterGraph,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&playback.graph)),"Create movie graph");
    checked(playback.graph->RenderFile(path.c_str(),nullptr),"Decode movie; a DirectShow decoder for this video format is required");
    checked(playback.graph.As(&playback.control),"Movie control");
    checked(playback.graph.As(&playback.video),"Movie video output");
    checked(playback.graph.As(&playback.events),"Movie events");
    checked(playback.video->put_Owner(reinterpret_cast<OAHWND>(owner)),"Attach movie to game");
    checked(playback.video->put_WindowStyle(WS_CHILD|WS_CLIPSIBLINGS|WS_CLIPCHILDREN),"Movie window style");
    checked(playback.video->put_MessageDrain(reinterpret_cast<OAHWND>(owner)),"Movie keyboard routing");
    checked(playback.video->put_Visible(OATRUE),"Show movie");
    checked(playback.control->Run(),"Start movie");
    for(;;){
        RECT client{};GetClientRect(owner,&client);
        checked(playback.video->SetWindowPosition(0,0,client.right,client.bottom),"Resize movie");
        long event=0;LONG_PTR first=0,second=0;
        while(SUCCEEDED(playback.events->GetEvent(&event,&first,&second,0))){
            playback.events->FreeEventParams(event,first,second);
            if(event==EC_COMPLETE)return 0;
            if(event==EC_ERRORABORT)checked(static_cast<HRESULT>(first),"Movie playback failed");
            if(event==EC_USERABORT)return 0;
        }
        MSG message{};
        while(PeekMessageW(&message,nullptr,0,0,PM_REMOVE)){
            if(browser_pretranslate(message)||input_pretranslate(message))continue;
            if(message.message==WM_QUIT)return 1;
            if(message.message==WM_KEYDOWN&&message.wParam==VK_F12)return 2;
            TranslateMessage(&message);DispatchMessageW(&message);
        }
        browser_pump();
        if(!IsWindow(owner))return 1;
        MsgWaitForMultipleObjectsEx(0,nullptr,15,QS_ALLINPUT,MWMO_INPUTAVAILABLE);
    }
}
VALUE play(VALUE,VALUE filename){
    StringValue(filename);const char* text=StringValueCStr(filename);
    int count=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,text,-1,nullptr,0);
    if(!count)rb_raise(rb_eArgError,"Movie path must be UTF-8");
    char failure[512]{};int outcome=0;
    {
        try{
            std::wstring path(count,L'\0');MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,text,-1,path.data(),count);path.pop_back();
            outcome=run(path);
        }catch(const std::exception& error){strncpy_s(failure,error.what(),_TRUNCATE);}
    }
    RB_GC_GUARD(filename);
    if(*failure)rb_raise(rb_path2class("RGSSError"),"Graphics.play_movie: %s",failure);
    if(outcome==1)rb_exit(0);
    if(outcome==2)rb_raise(rb_path2class("RGSSReset"),"reset");
    return Qnil;
}
}
void movie_attach(HWND window){owner=window;}
void init_movie(){rb_define_singleton_method(rb_define_module("Graphics"),"__play_movie",RUBY_METHOD_FUNC(play),1);}
