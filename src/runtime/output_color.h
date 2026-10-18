#pragma once
#include <windows.h>
#include <dxgi1_6.h>
#include <wrl/client.h>
#include <stdexcept>
#include <vector>

// Read the window's output only. FP16 scRGB white is 80 nits; SDR displays use display-relative white.
inline float output_white_scale(HMONITOR monitor) {
    if (!monitor) throw std::runtime_error("Output monitor is unavailable");
    Microsoft::WRL::ComPtr<IDXGIFactory1> factory;
    if (FAILED(CreateDXGIFactory1(IID_PPV_ARGS(&factory)))) throw std::runtime_error("Cannot refresh output color metadata");
    DXGI_OUTPUT_DESC1 desc{};
    bool found=false;
    for (UINT a=0; !found; ++a) {
        Microsoft::WRL::ComPtr<IDXGIAdapter1> adapter;
        HRESULT hr=factory->EnumAdapters1(a,&adapter);
        if (hr==DXGI_ERROR_NOT_FOUND) break;
        if (FAILED(hr)) throw std::runtime_error("Cannot enumerate display adapters");
        for (UINT o=0; ; ++o) {
            Microsoft::WRL::ComPtr<IDXGIOutput> output;
            hr=adapter->EnumOutputs(o,&output);
            if (hr==DXGI_ERROR_NOT_FOUND) break;
            Microsoft::WRL::ComPtr<IDXGIOutput6> advanced;
            if (FAILED(hr) || FAILED(output.As(&advanced)) || FAILED(advanced->GetDesc1(&desc)))
                throw std::runtime_error("Cannot read output color space");
            if (desc.AttachedToDesktop && desc.Monitor==monitor) { found=true; break; }
        }
    }
    if (!found) throw std::runtime_error("Window monitor has no DXGI output");
    if (desc.ColorSpace != DXGI_COLOR_SPACE_RGB_FULL_G2084_NONE_P2020) return 1.0f;
    for (int attempt=0; attempt<3; ++attempt) {
        UINT paths=0,modes=0;
        if (GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS,&paths,&modes)!=ERROR_SUCCESS)
            throw std::runtime_error("Cannot size active display paths");
        std::vector<DISPLAYCONFIG_PATH_INFO> path(paths);
        std::vector<DISPLAYCONFIG_MODE_INFO> mode(modes);
        LONG result=QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS,&paths,path.data(),&modes,mode.data(),nullptr);
        if (result==ERROR_INSUFFICIENT_BUFFER) continue;
        if (result!=ERROR_SUCCESS) throw std::runtime_error("Cannot read active display paths");
        for (UINT i=0; i<paths; ++i) {
            DISPLAYCONFIG_SOURCE_DEVICE_NAME source{};
            source.header.type=DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME;source.header.size=sizeof(source);
            source.header.adapterId=path[i].sourceInfo.adapterId;source.header.id=path[i].sourceInfo.id;
            if (DisplayConfigGetDeviceInfo(&source.header)!=ERROR_SUCCESS || _wcsicmp(source.viewGdiDeviceName,desc.DeviceName)) continue;
            struct White { DISPLAYCONFIG_DEVICE_INFO_HEADER header; ULONG level; };
            static_assert(sizeof(White)==24,"SDR white ABI");
            White white{};white.header.type=DISPLAYCONFIG_DEVICE_INFO_GET_SDR_WHITE_LEVEL;white.header.size=sizeof(white);
            white.header.adapterId=path[i].targetInfo.adapterId;white.header.id=path[i].targetInfo.id;
            if (DisplayConfigGetDeviceInfo(&white.header)!=ERROR_SUCCESS || !white.level)
                throw std::runtime_error("Cannot read HDR output SDR white level");
            return white.level/1000.0f;
        }
        throw std::runtime_error("HDR output has no matching active display path");
    }
    throw std::runtime_error("Display paths kept changing during color query");
}
