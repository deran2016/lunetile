#include <windows.h>
#include <d3d11.h>
#include <d3dcompiler.h>
#include <dxgi1_4.h>
#include <wrl/client.h>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <ruby.h>
#include "graphics.h"
#include "output_color.h"
#include "render_shader.h"

namespace {
using Microsoft::WRL::ComPtr;
void checked(HRESULT result, const char* operation) {
    if (FAILED(result)) { char error[160]; sprintf_s(error,"%s failed (HRESULT 0x%08lx)",operation,result); throw std::runtime_error(error); }
}
struct Surface {
    ComPtr<ID3D11Texture2D> texture;
    ComPtr<ID3D11RenderTargetView> target;
    ComPtr<ID3D11ShaderResourceView> view;
};
using rgss_render::Constants;
using rgss_render::shader;
struct Query { ComPtr<ID3D11Query> disjoint,start,end; bool pending=false; UINT64 sequence=0; };
UINT64 thread_cpu(){FILETIME create{},exit{},kernel{},user{};if(!GetThreadTimes(GetCurrentThread(),&create,&exit,&kernel,&user))return 0;ULARGE_INTEGER k{},u{};k.LowPart=kernel.dwLowDateTime;k.HighPart=kernel.dwHighDateTime;u.LowPart=user.dwLowDateTime;u.HighPart=user.dwHighDateTime;return k.QuadPart+u.QuadPart;}
struct Renderer {
    HWND window=nullptr;
    WNDPROC previous_proc=nullptr;
    DWORD window_style=0;
    RECT window_rect{};
    bool fullscreen=false;
    UINT back_width=640,back_height=480;
    HMONITOR color_monitor=nullptr;
    ULONGLONG color_checked=0;
    float white_scale=1.0f;
    DWORD owner=0;
    ComPtr<ID3D11Device> device;
    ComPtr<ID3D11DeviceContext> context;
    ComPtr<IDXGISwapChain> swap;
    ComPtr<ID3D11RenderTargetView> back;
    ComPtr<ID3D11VertexShader> vertex;
    ComPtr<ID3D11PixelShader> pixel;
    ComPtr<ID3D11Buffer> constants;
    ComPtr<ID3D11SamplerState> sampler;
    ComPtr<ID3D11RasterizerState> raster;
    ComPtr<ID3D11BlendState> blend[3],replace;
    Surface scene,group,frozen;
    std::array<Query,16> queries;
    unsigned int query_index=0;
    double gpu_ms=-1;
    UINT64 gpu_valid=0,gpu_invalid=0;
    UINT64 sequence=0,gpu_sequence=0,cpu_begin=0,last_cpu=0;
    bool frozen_valid=false,close=false,ready=false;
    LARGE_INTEGER frequency{},deadline{},last_end{};
    int rate=40,frame=0;
    int remainder=0;
    double wait_ms=0,render_ms=0;
    double script_cpu_ms=0,render_cpu_ms=0,wait_cpu_ms=0;
    double focus_pause_ms=0;
    HANDLE timer=nullptr;
    void surface(Surface& out) {
        D3D11_TEXTURE2D_DESC desc{};
        desc.Width=640;desc.Height=480;desc.MipLevels=desc.ArraySize=1;
        desc.Format=DXGI_FORMAT_R8G8B8A8_UNORM;desc.SampleDesc.Count=1;
        desc.BindFlags=D3D11_BIND_RENDER_TARGET|D3D11_BIND_SHADER_RESOURCE;
        checked(device->CreateTexture2D(&desc,nullptr,&out.texture),"Create surface");
        checked(device->CreateRenderTargetView(out.texture.Get(),nullptr,&out.target),"Create surface target");
        checked(device->CreateShaderResourceView(out.texture.Get(),nullptr,&out.view),"Create surface view");
    }
    void initialize() {
        if(ready) return;
        if(device) throw std::runtime_error("Renderer initialization previously failed");
        if(!window||!IsWindow(window)) throw std::runtime_error("Game window is unavailable");
        DXGI_SWAP_CHAIN_DESC desc{};
        desc.BufferDesc.Width=640;desc.BufferDesc.Height=480;
        // Explicit linear presentation avoids implicit SDR conversion and preserves output precision.
        desc.BufferDesc.Format=DXGI_FORMAT_R16G16B16A16_FLOAT;
        desc.SampleDesc.Count=1;desc.BufferCount=2;
        desc.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT;desc.OutputWindow=window;
        desc.Windowed=TRUE;desc.SwapEffect=DXGI_SWAP_EFFECT_FLIP_DISCARD;
        D3D_FEATURE_LEVEL level=D3D_FEATURE_LEVEL_11_0;
        checked(D3D11CreateDeviceAndSwapChain(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,&level,1,D3D11_SDK_VERSION,&desc,&swap,&device,nullptr,&context),"D3D11 hardware device");
        ComPtr<IDXGISwapChain3> color_swap;checked(swap.As(&color_swap),"Swap-chain color interface");
        UINT color_support=0;checked(color_swap->CheckColorSpaceSupport(DXGI_COLOR_SPACE_RGB_FULL_G10_NONE_P709,&color_support),"Linear output support query");
        if(!(color_support&DXGI_SWAP_CHAIN_COLOR_SPACE_SUPPORT_FLAG_PRESENT))throw std::runtime_error("Linear output color space unavailable");
        checked(color_swap->SetColorSpace1(DXGI_COLOR_SPACE_RGB_FULL_G10_NONE_P709),"Explicit linear output color space");
        // Our window procedure owns Alt+Enter and geometry; DXGI must not change them again.
        ComPtr<IDXGIFactory> factory;
        checked(swap->GetParent(IID_PPV_ARGS(&factory)),"Get swap-chain factory");
        checked(factory->MakeWindowAssociation(window,DXGI_MWA_NO_WINDOW_CHANGES),"Disable automatic DXGI window changes");
        ComPtr<ID3D11Texture2D> buffer;
        checked(swap->GetBuffer(0,IID_PPV_ARGS(&buffer)),"Get back buffer");
        checked(device->CreateRenderTargetView(buffer.Get(),nullptr,&back),"Back buffer target");

        ComPtr<ID3DBlob> vs,ps,error;
        checked(D3DCompile(shader,sizeof(shader)-1,nullptr,nullptr,nullptr,"vs","vs_4_0",D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&vs,&error),"Compile vertex shader");
        checked(D3DCompile(shader,sizeof(shader)-1,nullptr,nullptr,nullptr,"ps","ps_4_0",D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&ps,&error),"Compile pixel shader");
        checked(device->CreateVertexShader(vs->GetBufferPointer(),vs->GetBufferSize(),nullptr,&vertex),"Create vertex shader");
        checked(device->CreatePixelShader(ps->GetBufferPointer(),ps->GetBufferSize(),nullptr,&pixel),"Create pixel shader");
        D3D11_BUFFER_DESC buffer_desc{};buffer_desc.ByteWidth=sizeof(Constants);buffer_desc.Usage=D3D11_USAGE_DYNAMIC;
        buffer_desc.BindFlags=D3D11_BIND_CONSTANT_BUFFER;buffer_desc.CPUAccessFlags=D3D11_CPU_ACCESS_WRITE;
        checked(device->CreateBuffer(&buffer_desc,nullptr,&constants),"Create quad constants");
        D3D11_SAMPLER_DESC sample{};sample.Filter=D3D11_FILTER_MIN_MAG_MIP_POINT;
        sample.AddressU=sample.AddressV=sample.AddressW=D3D11_TEXTURE_ADDRESS_CLAMP;sample.MaxLOD=D3D11_FLOAT32_MAX;
        checked(device->CreateSamplerState(&sample,&sampler),"Create sampler");
        D3D11_RASTERIZER_DESC raster_desc{};raster_desc.FillMode=D3D11_FILL_SOLID;raster_desc.CullMode=D3D11_CULL_NONE;
        raster_desc.ScissorEnable=TRUE;raster_desc.DepthClipEnable=TRUE;
        checked(device->CreateRasterizerState(&raster_desc,&raster),"Create rasterizer");
        for(int i=0;i<3;++i){
            D3D11_BLEND_DESC blend_desc{};auto& b=blend_desc.RenderTarget[0];b.BlendEnable=TRUE;
            b.SrcBlend=D3D11_BLEND_SRC_ALPHA;b.DestBlend=i==0?D3D11_BLEND_INV_SRC_ALPHA:D3D11_BLEND_ONE;
            b.BlendOp=i==2?D3D11_BLEND_OP_REV_SUBTRACT:D3D11_BLEND_OP_ADD;
            b.SrcBlendAlpha=D3D11_BLEND_ONE;b.DestBlendAlpha=D3D11_BLEND_INV_SRC_ALPHA;b.BlendOpAlpha=D3D11_BLEND_OP_ADD;
            b.RenderTargetWriteMask=D3D11_COLOR_WRITE_ENABLE_ALL;
            checked(device->CreateBlendState(&blend_desc,&blend[i]),"Create blend state");
        }
        D3D11_BLEND_DESC copy_desc{};copy_desc.RenderTarget[0].RenderTargetWriteMask=D3D11_COLOR_WRITE_ENABLE_ALL;
        checked(device->CreateBlendState(&copy_desc,&replace),"Create copy blend");
        surface(scene);surface(group);surface(frozen);
        const float transparent[4]{};context->ClearRenderTargetView(scene.target.Get(),transparent);
        context->ClearRenderTargetView(frozen.target.Get(),transparent);
        for(auto& q:queries){
            D3D11_QUERY_DESC query{};query.Query=D3D11_QUERY_TIMESTAMP_DISJOINT;
            checked(device->CreateQuery(&query,&q.disjoint),"Create disjoint query");
            query.Query=D3D11_QUERY_TIMESTAMP;
            checked(device->CreateQuery(&query,&q.start),"Create timestamp query");
            checked(device->CreateQuery(&query,&q.end),"Create timestamp query");
        }
        timer=CreateWaitableTimerExW(nullptr,nullptr,CREATE_WAITABLE_TIMER_HIGH_RESOLUTION,TIMER_ALL_ACCESS);
        if(!timer) throw std::runtime_error("High resolution waitable timer unavailable");
        QueryPerformanceFrequency(&frequency);QueryPerformanceCounter(&deadline);last_end=deadline;
        ready=true;
    }
    void upload(Canvas* canvas){
        if(!canvas->texture){
            D3D11_TEXTURE2D_DESC desc{};desc.Width=canvas->width;desc.Height=canvas->height;
            desc.MipLevels=desc.ArraySize=1;desc.SampleDesc.Count=1;desc.Format=DXGI_FORMAT_R8G8B8A8_UNORM;
            desc.Usage=D3D11_USAGE_DEFAULT;desc.BindFlags=D3D11_BIND_SHADER_RESOURCE;
            D3D11_SUBRESOURCE_DATA initial{canvas->pixels,static_cast<UINT>(canvas->width*4),0};
            checked(device->CreateTexture2D(&desc,&initial,&canvas->texture),"Create bitmap texture");
            checked(device->CreateShaderResourceView(canvas->texture,nullptr,&canvas->view),"Create bitmap view");
        }else if(canvas->dirty){
            const auto& r=canvas->changed;
            D3D11_BOX box{static_cast<UINT>(r.left),static_cast<UINT>(r.top),0,static_cast<UINT>(r.right),static_cast<UINT>(r.bottom),1};
            context->UpdateSubresource(canvas->texture,0,&box,canvas->pixels+(static_cast<size_t>(r.top)*canvas->width+r.left)*4,canvas->width*4,0);
        }
        canvas->dirty=false;
    }
    void target(ID3D11RenderTargetView* out){
        ID3D11ShaderResourceView* clear[3]{};context->PSSetShaderResources(0,3,clear);
        context->OMSetRenderTargets(1,&out,nullptr);
    }
    void resize_back(){
        RECT client{};GetClientRect(window,&client);
        UINT width=std::max<LONG>(client.right,1),height=std::max<LONG>(client.bottom,1);
        if(width==back_width&&height==back_height)return;
        context->OMSetRenderTargets(0,nullptr,nullptr);back.Reset();
        checked(swap->ResizeBuffers(0,width,height,DXGI_FORMAT_UNKNOWN,0),"Resize window buffers");
        ComPtr<ID3D11Texture2D> buffer;checked(swap->GetBuffer(0,IID_PPV_ARGS(&buffer)),"Get resized buffer");
        checked(device->CreateRenderTargetView(buffer.Get(),nullptr,&back),"Resized window target");
        back_width=width;back_height=height;
    }
    void draw(ID3D11ShaderResourceView* image,Constants& values,const RECT& clip,int blend_mode=0,bool copy=false){
        D3D11_MAPPED_SUBRESOURCE mapped{};
        checked(context->Map(constants.Get(),0,D3D11_MAP_WRITE_DISCARD,0,&mapped),"Map quad constants");
        memcpy(mapped.pData,&values,sizeof(values));context->Unmap(constants.Get(),0);
        context->VSSetConstantBuffers(0,1,constants.GetAddressOf());context->PSSetConstantBuffers(0,1,constants.GetAddressOf());
        context->PSSetShaderResources(0,1,&image);context->RSSetScissorRects(1,&clip);
        context->OMSetBlendState(copy?replace.Get():blend[blend_mode].Get(),nullptr,0xffffffff);
        context->Draw(6,0);
    }
    void query_result(Query& q){
        if(!q.pending)return;
        D3D11_QUERY_DATA_TIMESTAMP_DISJOINT status{};UINT64 start=0,end=0;
        HRESULT a=context->GetData(q.disjoint.Get(),&status,sizeof(status),D3D11_ASYNC_GETDATA_DONOTFLUSH);
        HRESULT b=context->GetData(q.start.Get(),&start,sizeof(start),D3D11_ASYNC_GETDATA_DONOTFLUSH);
        HRESULT c=context->GetData(q.end.Get(),&end,sizeof(end),D3D11_ASYNC_GETDATA_DONOTFLUSH);
        if(a==S_OK&&b==S_OK&&c==S_OK){
            q.pending=false;
            gpu_sequence=q.sequence;
            if(!status.Disjoint&&status.Frequency&&end>=start){gpu_ms=1000.0*(end-start)/status.Frequency;++gpu_valid;}
            else{gpu_ms=-1;++gpu_invalid;}
        }else if(FAILED(a)||FAILED(b)||FAILED(c)){q.pending=false;gpu_ms=-1;++gpu_invalid;}
    }
};
Renderer renderer;
LRESULT CALLBACK window_proc(HWND window,UINT message,WPARAM wparam,LPARAM lparam){
    input_message(message,wparam);
    if(message==WM_SYSKEYDOWN&&wparam==VK_RETURN&&(lparam&(1<<29))&&!(lparam&(1<<30))){
        auto& r=renderer;
        if(!r.fullscreen){
            r.window_style=static_cast<DWORD>(GetWindowLongPtrW(window,GWL_STYLE));GetWindowRect(window,&r.window_rect);
            MONITORINFO monitor{sizeof(MONITORINFO)};GetMonitorInfoW(MonitorFromWindow(window,MONITOR_DEFAULTTONEAREST),&monitor);
            if(!monitor.rcMonitor.right&&!monitor.rcMonitor.bottom)return 0;
            SetWindowLongPtrW(window,GWL_STYLE,(r.window_style&~WS_OVERLAPPEDWINDOW)|WS_POPUP);
            if(!SetWindowPos(window,nullptr,monitor.rcMonitor.left,monitor.rcMonitor.top,monitor.rcMonitor.right-monitor.rcMonitor.left,monitor.rcMonitor.bottom-monitor.rcMonitor.top,SWP_FRAMECHANGED|SWP_NOZORDER))return 0;
        }else{
            SetWindowLongPtrW(window,GWL_STYLE,r.window_style);
            SetWindowPos(window,nullptr,r.window_rect.left,r.window_rect.top,r.window_rect.right-r.window_rect.left,r.window_rect.bottom-r.window_rect.top,SWP_FRAMECHANGED|SWP_NOZORDER);
        }
        r.fullscreen=!r.fullscreen;return 0;
    }
    // This engine owns geometry and fullscreen handling; restore the launcher procedure at teardown.
    return DefWindowProcW(window,message,wparam,lparam);
}
float number(VALUE array,long index){return static_cast<float>(NUM2DBL(rb_ary_entry(array,index)));}
float property(VALUE value,const char* name){return static_cast<float>(NUM2DBL(rb_funcall(value,rb_intern(name),0)));}
RECT rectangle(VALUE value){return {static_cast<LONG>(property(value,"x")),static_cast<LONG>(property(value,"y")),static_cast<LONG>(property(value,"x")+property(value,"width")),static_cast<LONG>(property(value,"y")+property(value,"height"))};}
void effect(Constants& state,VALUE color,VALUE tone){
    if(!NIL_P(color)){state.color[0]=property(color,"red")/255;state.color[1]=property(color,"green")/255;state.color[2]=property(color,"blue")/255;state.color[3]=property(color,"alpha")/255;}
    if(!NIL_P(tone)){state.tone[0]=property(tone,"red")/255;state.tone[1]=property(tone,"green")/255;state.tone[2]=property(tone,"blue")/255;state.tone[3]=property(tone,"gray")/255;}
}
Constants screen(){Constants s{};s.position[2]=640;s.position[3]=480;s.source[2]=s.source[3]=1;s.transform[0]=s.transform[1]=s.transform[2]=1;s.origin[2]=1;return s;}
VALUE present(VALUE,VALUE commands,VALUE progress,VALUE mask_value,VALUE vague){
    Check_Type(commands,T_ARRAY);
    if(GetCurrentThreadId()!=renderer.owner)rb_raise(rb_eThreadError,"Graphics requires the game thread");
    // Parse Ruby objects before C++ resources are acquired; no exception crosses a C++ owner.
    struct Draw {int kind;Canvas* bitmap;Constants state;RECT clip;int blend;};
    long count=RARRAY_LEN(commands);
    if(count>100000)rb_raise(rb_eArgError,"Too many rendering commands");
    VALUE storage=rb_str_new(nullptr,count*sizeof(Draw));
    auto* draws=reinterpret_cast<Draw*>(RSTRING_PTR(storage));
    RECT viewport{0,0,640,480};
    for(long i=0;i<count;++i){
        VALUE command=rb_ary_entry(commands,i);Check_Type(command,T_ARRAY);
        Draw& d=draws[i];memset(&d,0,sizeof(d));d.kind=NUM2INT(rb_ary_entry(command,0));d.state=screen();d.clip=viewport;
        if(d.kind==0){
            if(RARRAY_LEN(command)!=22)rb_raise(rb_eArgError,"Invalid quad command");
            d.bitmap=canvas_get(rb_ary_entry(command,1));
            d.state.position[0]=number(command,2);d.state.position[1]=number(command,3);d.state.position[2]=number(command,4);d.state.position[3]=number(command,5);
            d.state.source[0]=number(command,6)/d.bitmap->width;d.state.source[1]=number(command,7)/d.bitmap->height;
            d.state.source[2]=number(command,8)/d.bitmap->width;d.state.source[3]=number(command,9)/d.bitmap->height;
            d.state.transform[0]=number(command,10);d.state.transform[1]=number(command,11);
            double angle=-number(command,12)*3.141592653589793/180;
            d.state.transform[2]=static_cast<float>(cos(angle));d.state.transform[3]=static_cast<float>(sin(angle));
            d.state.origin[0]=number(command,13);d.state.origin[1]=number(command,14);d.state.origin[2]=number(command,15)/255;d.state.origin[3]=number(command,19);
            d.blend=NUM2INT(rb_ary_entry(command,16));if(d.blend<0||d.blend>2)rb_raise(rb_eArgError,"Invalid blend mode");
            effect(d.state,rb_ary_entry(command,17),rb_ary_entry(command,18));
            VALUE clip=rb_ary_entry(command,20);if(!NIL_P(clip)){RECT area=rectangle(clip);IntersectRect(&d.clip,&viewport,&area);}
            d.state.extra[1]=RTEST(rb_ary_entry(command,21))?1.0f:0.0f;
        }else if(d.kind==1){viewport=rectangle(rb_ary_entry(command,1));RECT full{0,0,640,480};IntersectRect(&viewport,&viewport,&full);d.clip=viewport;}
        else if(d.kind==2){effect(d.state,rb_ary_entry(command,2),rb_ary_entry(command,3));d.state.extra[0]=1;d.clip=viewport;viewport={0,0,640,480};}
        else rb_raise(rb_eArgError,"Unknown rendering command");
    }
    Canvas* mask=NIL_P(mask_value)?nullptr:canvas_get(mask_value);
    float fade=static_cast<float>(NUM2DBL(progress)),fuzz=static_cast<float>(NUM2DBL(vague));
    char failure[256]{};
    {
        try{
            auto& r=renderer;r.initialize();LARGE_INTEGER start{};QueryPerformanceCounter(&start);r.resize_back();
            HMONITOR monitor=MonitorFromWindow(r.window,MONITOR_DEFAULTTONEAREST);ULONGLONG now=GetTickCount64();
            if(monitor!=r.color_monitor||now-r.color_checked>=1000){r.white_scale=output_white_scale(monitor);r.color_monitor=monitor;r.color_checked=now;}
            r.query_result(r.queries[r.query_index]);auto& q=r.queries[r.query_index];bool queried=!q.pending;
            if(queried){q.sequence=r.sequence;r.context->Begin(q.disjoint.Get());r.context->End(q.start.Get());}
            r.context->IASetInputLayout(nullptr);r.context->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
            r.context->VSSetShader(r.vertex.Get(),nullptr,0);r.context->PSSetShader(r.pixel.Get(),nullptr,0);
            r.context->PSSetSamplers(0,1,r.sampler.GetAddressOf());r.context->RSSetState(r.raster.Get());
            D3D11_VIEWPORT full{0,0,640,480,0,1};r.context->RSSetViewports(1,&full);
            r.target(r.scene.target.Get());const float black[4]={0,0,0,1};r.context->ClearRenderTargetView(r.scene.target.Get(),black);
            for(long i=0;i<count;++i){auto& d=draws[i];
                if(d.kind==0){r.upload(d.bitmap);r.draw(d.bitmap->view,d.state,d.clip,d.blend);}
                else if(d.kind==1){r.target(r.group.target.Get());const float clear[4]{};r.context->ClearRenderTargetView(r.group.target.Get(),clear);}
                else{
                    r.target(r.scene.target.Get());Constants contents=d.state;
                    memset(contents.color,0,sizeof(contents.color));r.draw(r.group.view.Get(),contents,d.clip);
                    if(d.state.color[3]>0){Constants overlay=screen();memcpy(overlay.color,d.state.color,sizeof(overlay.color));overlay.extra[0]=3;r.draw(r.group.view.Get(),overlay,d.clip);}
                }
            }
            r.target(r.back.Get());r.context->ClearRenderTargetView(r.back.Get(),black);
            float scale=std::min(r.back_width/640.0f,r.back_height/480.0f);
            D3D11_VIEWPORT fitted{(r.back_width-640*scale)/2,(r.back_height-480*scale)/2,640*scale,480*scale,0,1};r.context->RSSetViewports(1,&fitted);
            Constants copy=screen();copy.extra[0]=4;copy.color[0]=r.white_scale;RECT clip{0,0,static_cast<LONG>(r.back_width),static_cast<LONG>(r.back_height)};
            if(fade>=0&&r.frozen_valid){copy.extra[0]=2;copy.extra[2]=fade;copy.extra[3]=mask?fuzz:-1;
                ID3D11ShaderResourceView* resources[2]={r.frozen.view.Get(),nullptr};if(mask){r.upload(mask);resources[1]=mask->view;}
                r.context->PSSetShaderResources(1,2,resources);
            }
            r.draw(r.scene.view.Get(),copy,clip,0,true);
            if(queried){r.context->End(q.end.Get());r.context->End(q.disjoint.Get());q.pending=true;}
            r.query_index=(r.query_index+1)%r.queries.size();
            checked(r.swap->Present(0,0),"Present");LARGE_INTEGER end{};QueryPerformanceCounter(&end);
            r.render_ms=1000.0*(end.QuadPart-start.QuadPart)/r.frequency.QuadPart;
            r.render_cpu_ms=r.cpu_begin?(thread_cpu()-r.cpu_begin)/10000.0:0;
            ++r.sequence;
        }catch(const std::exception& e){strncpy_s(failure,e.what(),_TRUNCATE);}
    }
    RB_GC_GUARD(storage);RB_GC_GUARD(commands);RB_GC_GUARD(mask_value);
    if(*failure)rb_raise(rb_path2class("RGSSError"),"%s",failure);
    return Qnil;
}
bool pump(){
    MSG message{};while(PeekMessageW(&message,nullptr,0,0,PM_REMOVE)){if(message.message==WM_QUIT)renderer.close=true;TranslateMessage(&message);DispatchMessageW(&message);}
    if(renderer.close||!IsWindow(renderer.window))return false;
    if(input_take_reset()){
        ID name=rb_intern("Reset");VALUE klass=rb_const_defined_at(rb_cObject,name)?rb_const_get_at(rb_cObject,name):rb_define_class("Reset",rb_eException);
        rb_exc_raise(rb_exc_new_cstr(klass,""));
    }
    return true;
}
VALUE tick(VALUE){
    auto& r=renderer;
    if(GetCurrentThreadId()!=r.owner)rb_raise(rb_eThreadError,"Graphics requires the game thread");
    if(!pump())rb_exit(0);
    r.focus_pause_ms=0;
    if(GetForegroundWindow()!=r.window){
        LARGE_INTEGER paused{},resumed{};QueryPerformanceCounter(&paused);
        do{MsgWaitForMultipleObjectsEx(0,nullptr,100,QS_ALLINPUT,MWMO_INPUTAVAILABLE);if(!pump())rb_exit(0);}while(GetForegroundWindow()!=r.window);
        QueryPerformanceCounter(&resumed);
        if(r.frequency.QuadPart)r.focus_pause_ms=1000.0*(resumed.QuadPart-paused.QuadPart)/r.frequency.QuadPart;
        r.deadline=resumed;r.remainder=0;
    }
    UINT64 cpu=thread_cpu();LARGE_INTEGER start{},now{};QueryPerformanceCounter(&start);
    if(!r.frequency.QuadPart){QueryPerformanceFrequency(&r.frequency);r.deadline=start;}
    LONGLONG interval=r.frequency.QuadPart/r.rate;
    if(start.QuadPart-r.deadline.QuadPart>r.frequency.QuadPart/4)r.deadline=start;
    r.deadline.QuadPart+=interval;
    r.remainder+=static_cast<int>(r.frequency.QuadPart%r.rate);
    if(r.remainder>=r.rate){++r.deadline.QuadPart;r.remainder-=r.rate;}
    for(;;){
        QueryPerformanceCounter(&now);LONGLONG remaining=r.deadline.QuadPart-now.QuadPart;if(remaining<=0)break;
        LARGE_INTEGER due{};due.QuadPart=-std::max<LONGLONG>(1,remaining*10000000/r.frequency.QuadPart);
        if(r.timer&&SetWaitableTimer(r.timer,&due,0,nullptr,nullptr,FALSE))MsgWaitForMultipleObjectsEx(1,&r.timer,INFINITE,QS_ALLINPUT,MWMO_INPUTAVAILABLE);
        else MsgWaitForMultipleObjectsEx(0,nullptr,static_cast<DWORD>(std::max<LONGLONG>(1,remaining*1000/r.frequency.QuadPart)),QS_ALLINPUT,MWMO_INPUTAVAILABLE);
        if(!pump())rb_exit(0);
    }
    r.wait_ms=1000.0*(now.QuadPart-start.QuadPart)/r.frequency.QuadPart;r.last_end=now;r.last_cpu=thread_cpu();r.wait_cpu_ms=(r.last_cpu-cpu)/10000.0;++r.frame;return Qnil;
}
VALUE freeze_frame(VALUE){char failure[256]{};{try{renderer.initialize();ID3D11ShaderResourceView* empty[3]{};renderer.context->PSSetShaderResources(0,3,empty);renderer.context->CopyResource(renderer.frozen.texture.Get(),renderer.scene.texture.Get());renderer.frozen_valid=true;}catch(const std::exception& e){strncpy_s(failure,e.what(),_TRUNCATE);}}if(*failure)rb_raise(rb_path2class("RGSSError"),"%s",failure);return Qnil;}
VALUE frame_count(VALUE){return INT2NUM(renderer.frame);}
VALUE set_frame_count(VALUE,VALUE count){renderer.frame=NUM2INT(count);return count;}
VALUE frame_rate(VALUE){return INT2NUM(renderer.rate);}
VALUE set_frame_rate(VALUE,VALUE rate){int value=NUM2INT(rate);if(value<10||value>120)rb_raise(rb_eArgError,"Frame rate must be 10..120");renderer.rate=value;renderer.remainder=0;QueryPerformanceCounter(&renderer.deadline);return rate;}
VALUE reset_deadline(VALUE){QueryPerformanceCounter(&renderer.deadline);renderer.remainder=0;return Qnil;}
VALUE begin_frame(VALUE){renderer.cpu_begin=thread_cpu();renderer.script_cpu_ms=renderer.last_cpu?(renderer.cpu_begin-renderer.last_cpu)/10000.0:0;return Qnil;}
VALUE stats(VALUE){return rb_ary_new_from_args(11,DBL2NUM(renderer.render_ms),DBL2NUM(renderer.wait_ms),renderer.gpu_ms>=0?DBL2NUM(renderer.gpu_ms):Qnil,ULL2NUM(renderer.gpu_valid),ULL2NUM(renderer.gpu_invalid),DBL2NUM(renderer.script_cpu_ms),DBL2NUM(renderer.render_cpu_ms),DBL2NUM(renderer.wait_cpu_ms),ULL2NUM(renderer.sequence),renderer.gpu_valid?ULL2NUM(renderer.gpu_sequence):Qnil,DBL2NUM(renderer.focus_pause_ms));}
VALUE scene_pixel(VALUE,VALUE vx,VALUE vy){
    int x=NUM2INT(vx),y=NUM2INT(vy);if(x<0||y<0||x>=640||y>=480)rb_raise(rb_eArgError,"Pixel is outside the scene");
    unsigned char bytes[4]{};char failure[256]{};
    {
        try{
            auto& r=renderer;r.initialize();ComPtr<ID3D11Texture2D> staging;
            D3D11_TEXTURE2D_DESC desc{};desc.Width=desc.Height=desc.MipLevels=desc.ArraySize=1;
            desc.Format=DXGI_FORMAT_R8G8B8A8_UNORM;desc.SampleDesc.Count=1;desc.Usage=D3D11_USAGE_STAGING;desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
            checked(r.device->CreateTexture2D(&desc,nullptr,&staging),"Create diagnostic readback");
            D3D11_BOX box{static_cast<UINT>(x),static_cast<UINT>(y),0,static_cast<UINT>(x+1),static_cast<UINT>(y+1),1};
            r.context->CopySubresourceRegion(staging.Get(),0,0,0,0,r.scene.texture.Get(),0,&box);
            D3D11_MAPPED_SUBRESOURCE data{};checked(r.context->Map(staging.Get(),0,D3D11_MAP_READ,0,&data),"Read scene pixel");
            memcpy(bytes,data.pData,4);r.context->Unmap(staging.Get(),0);
        }catch(const std::exception& e){strncpy_s(failure,e.what(),_TRUNCATE);}
    }
    if(*failure)rb_raise(rb_path2class("RGSSError"),"%s",failure);
    return rb_ary_new_from_args(4,INT2NUM(bytes[0]),INT2NUM(bytes[1]),INT2NUM(bytes[2]),INT2NUM(bytes[3]));
}
}

void graphics_attach(HWND window){renderer.window=window;renderer.owner=GetCurrentThreadId();input_attach(window);renderer.previous_proc=reinterpret_cast<WNDPROC>(SetWindowLongPtrW(window,GWLP_WNDPROC,reinterpret_cast<LONG_PTR>(window_proc)));SetForegroundWindow(window);}
void graphics_shutdown(){if(renderer.window&&IsWindow(renderer.window)&&renderer.previous_proc)SetWindowLongPtrW(renderer.window,GWLP_WNDPROC,reinterpret_cast<LONG_PTR>(renderer.previous_proc));if(renderer.timer){CloseHandle(renderer.timer);renderer.timer=nullptr;}renderer.context.Reset();renderer=Renderer{};}
void graphics_reset(){
    auto& r=renderer;r.rate=40;r.remainder=0;r.frozen_valid=false;QueryPerformanceCounter(&r.deadline);
    if(r.context){float black[4]={0,0,0,1};if(r.scene.target)r.context->ClearRenderTargetView(r.scene.target.Get(),black);if(r.frozen.target)r.context->ClearRenderTargetView(r.frozen.target.Get(),black);}
    input_reset();
}
void init_graphics(){
    VALUE graphics=rb_define_module("Graphics");
    rb_define_singleton_method(graphics,"__present",RUBY_METHOD_FUNC(present),4);
    rb_define_singleton_method(graphics,"__begin",RUBY_METHOD_FUNC(begin_frame),0);
    rb_define_singleton_method(graphics,"__tick",RUBY_METHOD_FUNC(tick),0);
    rb_define_singleton_method(graphics,"freeze",RUBY_METHOD_FUNC(freeze_frame),0);
    rb_define_singleton_method(graphics,"frame_count",RUBY_METHOD_FUNC(frame_count),0);
    rb_define_singleton_method(graphics,"frame_count=",RUBY_METHOD_FUNC(set_frame_count),1);
    rb_define_singleton_method(graphics,"frame_rate",RUBY_METHOD_FUNC(frame_rate),0);
    rb_define_singleton_method(graphics,"frame_rate=",RUBY_METHOD_FUNC(set_frame_rate),1);
    rb_define_singleton_method(graphics,"frame_reset",RUBY_METHOD_FUNC(reset_deadline),0);
    rb_define_singleton_method(graphics,"__timings",RUBY_METHOD_FUNC(stats),0);
    rb_define_singleton_method(graphics,"__scene_pixel",RUBY_METHOD_FUNC(scene_pixel),2);
}
