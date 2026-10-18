// Read-only display color metadata; no settings, DPI query, screenshot or input injection.
#include <windows.h>
#include <dxgi1_6.h>
#include <wrl/client.h>
#include <cstdio>
#include <vector>
using Microsoft::WRL::ComPtr;
int main(){
    ComPtr<IDXGIFactory1> factory;
    if(FAILED(CreateDXGIFactory1(IID_PPV_ARGS(&factory))))return 1;
    bool first=true;unsigned attached=0;std::puts("{\"outputs\":[");
    for(UINT a=0;;++a){ComPtr<IDXGIAdapter1> adapter;HRESULT hr=factory->EnumAdapters1(a,&adapter);if(hr==DXGI_ERROR_NOT_FOUND)break;if(FAILED(hr))return 2;
        for(UINT o=0;;++o){ComPtr<IDXGIOutput> output;hr=adapter->EnumOutputs(o,&output);if(hr==DXGI_ERROR_NOT_FOUND)break;if(FAILED(hr))return 3;
            ComPtr<IDXGIOutput6> advanced;DXGI_OUTPUT_DESC1 desc{};
            if(FAILED(output.As(&advanced))||FAILED(advanced->GetDesc1(&desc)))return 4;
            if(desc.AttachedToDesktop)++attached;
            std::printf("%s{\"adapter\":%u,\"output\":%u,\"attached\":%s,\"bits_per_color\":%u,\"color_space\":%u,\"min_nits\":%.6f,\"max_nits\":%.6f,\"max_full_frame_nits\":%.6f}",first?"":",\n",a,o,desc.AttachedToDesktop?"true":"false",desc.BitsPerColor,static_cast<unsigned>(desc.ColorSpace),desc.MinLuminance,desc.MaxLuminance,desc.MaxFullFrameLuminance);first=false;
        }
    }
    std::printf("\n],\"attached_count\":%u,\"sdr_white\":[",attached);
    UINT paths=0,modes=0;if(GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS,&paths,&modes)!=ERROR_SUCCESS)return 6;
    std::vector<DISPLAYCONFIG_PATH_INFO> path(paths);std::vector<DISPLAYCONFIG_MODE_INFO> mode(modes);
    if(QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS,&paths,path.data(),&modes,mode.data(),nullptr)!=ERROR_SUCCESS)return 7;
    first=true;
    for(UINT i=0;i<paths;++i){
        struct White {DISPLAYCONFIG_DEVICE_INFO_HEADER header;ULONG level;};static_assert(sizeof(White)==24,"SDR white ABI");
        White white{};white.header.type=DISPLAYCONFIG_DEVICE_INFO_GET_SDR_WHITE_LEVEL;white.header.size=sizeof(white);white.header.adapterId=path[i].targetInfo.adapterId;white.header.id=path[i].targetInfo.id;
        LONG result=DisplayConfigGetDeviceInfo(&white.header);
        std::printf("%s{\"path\":%u,\"result\":%ld,\"level\":%lu}",first?"":",",i,result,white.level);first=false;
    }
    std::puts("]}");return attached?0:5;
}
