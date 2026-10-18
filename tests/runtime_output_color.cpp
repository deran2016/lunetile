// Hidden-window GPU regression: the production shader, real FP16 back buffer and read-only OS white level.
#include <windows.h>
#include <d3d11.h>
#include <d3dcompiler.h>
#include <DirectXPackedVector.h>
#include <wrl/client.h>
#include <array>
#include <cmath>
#include <cstdio>
#include <stdexcept>
#include "../src/runtime/output_color.h"
#include "../src/runtime/render_shader.h"
using Microsoft::WRL::ComPtr;
void check(HRESULT hr){if(FAILED(hr))throw std::runtime_error("D3D11 color probe failed");}
float linear(float x){return x<=0.04045f?x/12.92f:std::pow((x+0.055f)/1.055f,2.4f);}
int main(){
    HWND window=nullptr;
    try {
        WNDCLASSW cls{};cls.lpfnWndProc=DefWindowProcW;cls.hInstance=GetModuleHandleW(nullptr);cls.lpszClassName=L"RGSSXP hidden color regression";
        if(!RegisterClassW(&cls))throw std::runtime_error("Color probe class registration failed");
        window=CreateWindowW(cls.lpszClassName,L"RGSSXP hidden color regression",WS_OVERLAPPEDWINDOW,0,0,640,480,nullptr,nullptr,cls.hInstance,nullptr);
        if(!window)throw std::runtime_error("Color probe window creation failed");
        DXGI_SWAP_CHAIN_DESC desc{};desc.BufferDesc.Width=640;desc.BufferDesc.Height=480;desc.BufferDesc.Format=DXGI_FORMAT_R16G16B16A16_FLOAT;
        desc.SampleDesc.Count=1;desc.BufferCount=2;desc.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT;desc.OutputWindow=window;
        desc.Windowed=TRUE;desc.SwapEffect=DXGI_SWAP_EFFECT_FLIP_DISCARD;
        ComPtr<ID3D11Device> device;ComPtr<ID3D11DeviceContext> context;ComPtr<IDXGISwapChain> swap;
        D3D_FEATURE_LEVEL level=D3D_FEATURE_LEVEL_11_0;
        check(D3D11CreateDeviceAndSwapChain(nullptr,D3D_DRIVER_TYPE_HARDWARE,nullptr,0,&level,1,D3D11_SDK_VERSION,&desc,&swap,&device,nullptr,&context));
        ComPtr<IDXGISwapChain3> colors;check(swap.As(&colors));UINT support=0;
        check(colors->CheckColorSpaceSupport(DXGI_COLOR_SPACE_RGB_FULL_G10_NONE_P709,&support));
        if(!(support&DXGI_SWAP_CHAIN_COLOR_SPACE_SUPPORT_FLAG_PRESENT))throw std::runtime_error("FP16 linear presentation not supported");
        check(colors->SetColorSpace1(DXGI_COLOR_SPACE_RGB_FULL_G10_NONE_P709));
        float os_scale=output_white_scale(MonitorFromWindow(window,MONITOR_DEFAULTTONEAREST));
        bool invalid_rejected=false;try{output_white_scale(nullptr);}catch(const std::runtime_error&){invalid_rejected=true;}
        if(!invalid_rejected)throw std::runtime_error("Missing output was silently accepted");
        ComPtr<ID3D11Texture2D> back,readback;check(swap->GetBuffer(0,IID_PPV_ARGS(&back)));
        ComPtr<ID3D11RenderTargetView> target;check(device->CreateRenderTargetView(back.Get(),nullptr,&target));
        D3D11_TEXTURE2D_DESC td{};back->GetDesc(&td);td.Usage=D3D11_USAGE_STAGING;td.BindFlags=0;td.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
        check(device->CreateTexture2D(&td,nullptr,&readback));
        std::array<unsigned char,640*4> pixels{},previous{};
        for(unsigned x=0;x<640;++x){pixels[x*4]=static_cast<unsigned char>(x%256);pixels[x*4+1]=static_cast<unsigned char>(255-x%256);pixels[x*4+2]=128;pixels[x*4+3]=255;
            previous[x*4]=pixels[x*4+1];previous[x*4+1]=64;previous[x*4+2]=192;previous[x*4+3]=255;}
        td={};td.Width=640;td.Height=1;td.MipLevels=td.ArraySize=1;td.Format=DXGI_FORMAT_R8G8B8A8_UNORM;td.SampleDesc.Count=1;td.BindFlags=D3D11_BIND_SHADER_RESOURCE;
        D3D11_SUBRESOURCE_DATA initial{pixels.data(),640*4,0};
        ComPtr<ID3D11Texture2D> image;ComPtr<ID3D11ShaderResourceView> view;
        check(device->CreateTexture2D(&td,&initial,&image));check(device->CreateShaderResourceView(image.Get(),nullptr,&view));
        ComPtr<ID3D11Texture2D> old_image;ComPtr<ID3D11ShaderResourceView> old_view;initial.pSysMem=previous.data();
        check(device->CreateTexture2D(&td,&initial,&old_image));check(device->CreateShaderResourceView(old_image.Get(),nullptr,&old_view));
        ComPtr<ID3DBlob> vs,ps,error;
        check(D3DCompile(rgss_render::shader,sizeof(rgss_render::shader)-1,nullptr,nullptr,nullptr,"vs","vs_4_0",D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&vs,&error));
        check(D3DCompile(rgss_render::shader,sizeof(rgss_render::shader)-1,nullptr,nullptr,nullptr,"ps","ps_4_0",D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&ps,&error));
        ComPtr<ID3D11VertexShader> vertex;ComPtr<ID3D11PixelShader> pixel;
        check(device->CreateVertexShader(vs->GetBufferPointer(),vs->GetBufferSize(),nullptr,&vertex));check(device->CreatePixelShader(ps->GetBufferPointer(),ps->GetBufferSize(),nullptr,&pixel));
        ComPtr<ID3D11SamplerState> sampler;D3D11_SAMPLER_DESC sd{};sd.Filter=D3D11_FILTER_MIN_MAG_MIP_POINT;
        sd.AddressU=sd.AddressV=sd.AddressW=D3D11_TEXTURE_ADDRESS_CLAMP;sd.MaxLOD=D3D11_FLOAT32_MAX;check(device->CreateSamplerState(&sd,&sampler));
        ComPtr<ID3D11RasterizerState> raster;D3D11_RASTERIZER_DESC rd{};rd.FillMode=D3D11_FILL_SOLID;rd.CullMode=D3D11_CULL_NONE;rd.DepthClipEnable=TRUE;check(device->CreateRasterizerState(&rd,&raster));
        ComPtr<ID3D11Buffer> buffer;D3D11_BUFFER_DESC bd{};bd.ByteWidth=sizeof(rgss_render::Constants);bd.Usage=D3D11_USAGE_DEFAULT;bd.BindFlags=D3D11_BIND_CONSTANT_BUFFER;check(device->CreateBuffer(&bd,nullptr,&buffer));
        context->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);context->VSSetShader(vertex.Get(),nullptr,0);context->PSSetShader(pixel.Get(),nullptr,0);
        context->VSSetConstantBuffers(0,1,buffer.GetAddressOf());context->PSSetConstantBuffers(0,1,buffer.GetAddressOf());context->PSSetSamplers(0,1,sampler.GetAddressOf());context->RSSetState(raster.Get());
        D3D11_VIEWPORT viewport{0,0,640,480,0,1};context->RSSetViewports(1,&viewport);context->OMSetRenderTargets(1,target.GetAddressOf(),nullptr);
        ID3D11ShaderResourceView* resources[3]={view.Get(),old_view.Get(),view.Get()};context->PSSetShaderResources(0,3,resources);
        unsigned checked_pixels=0;
        for(int phase: {0,1,2,3}) for(float scale: {1.0f,os_scale}) {
            rgss_render::Constants state{};state.position[2]=640;state.position[3]=480;state.source[2]=state.source[3]=1;
            state.transform[0]=state.transform[1]=state.transform[2]=state.origin[2]=1;state.extra[0]=phase==0?0.0f:phase==1?4.0f:2.0f;state.color[0]=scale;
            state.extra[2]=0.5f;state.extra[3]=phase==3?0.4f:-1.0f;
            context->UpdateSubresource(buffer.Get(),0,nullptr,&state,0,0);context->Draw(6,0);
            context->CopyResource(readback.Get(),back.Get());D3D11_MAPPED_SUBRESOURCE mapped{};check(context->Map(readback.Get(),0,D3D11_MAP_READ,0,&mapped));
            const auto* halves=static_cast<const uint16_t*>(mapped.pData);
            for(unsigned x=0;x<256;++x)for(unsigned c=0;c<4;++c){
                float value=pixels[x*4+c]/255.0f;
                if(phase>=2){float blend=phase==3?std::max(0.0f,std::min(1.0f,(0.7f-pixels[x*4]/255.0f)/0.4f)):0.5f;float before=previous[x*4+c]/255.0f;value=before+(value-before)*blend;}
                float expected=c<3&&phase!=0?linear(value)*scale:value;
                float observed=DirectX::PackedVector::XMConvertHalfToFloat(halves[x*4+c]);
                if(std::abs(observed-expected)>std::max(0.0001f,std::abs(expected)*0.001f))throw std::runtime_error("Output gamma, SDR white scale, alpha or encoded-space preservation mismatch");
                ++checked_pixels;
            }
            context->Unmap(readback.Get(),0);
        }
        std::printf("PASS: %u GPU channel values; FP16/G10 output, encoded scene preservation, final transition conversion; OS white scale=%.6f. Hidden window only; no physical-display verdict.\n",checked_pixels,os_scale);
        DestroyWindow(window);return 0;
    }catch(const std::exception& e){if(window)DestroyWindow(window);std::fprintf(stderr,"%s\n",e.what());return 1;}
}
