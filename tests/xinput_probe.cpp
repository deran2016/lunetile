// Test-only imports in the owned game process; never packaged or installed as a driver.
#include <windows.h>
#include <Xinput.h>
#include <cstdio>

namespace {
HWND window=nullptr;
DWORD port=2,packet=0;
bool foreground=true,connected=true;
XINPUT_GAMEPAD pad{};
WORD left=0,right=0;
DWORD WINAPI get_state(DWORD index,XINPUT_STATE* state){
    if(!connected||index!=port)return ERROR_DEVICE_NOT_CONNECTED;
    state->dwPacketNumber=++packet;state->Gamepad=pad;return ERROR_SUCCESS;
}
DWORD WINAPI set_state(DWORD index,XINPUT_VIBRATION* state){
    if(!connected||index!=port)return ERROR_DEVICE_NOT_CONNECTED;
    left=state->wLeftMotorSpeed;right=state->wRightMotorSpeed;
    FILE* file=nullptr;
    if(!fopen_s(&file,"xinput-motors.txt","w")){fprintf(file,"%u,%u",left,right);fclose(file);}
    return ERROR_SUCCESS;
}
HWND WINAPI get_foreground(){return foreground?window:nullptr;}
BOOL CALLBACK find_window(HWND value,LPARAM){
    RECT rect{};GetClientRect(value,&rect);
    if(IsWindowVisible(value)&&rect.right>=300&&rect.bottom>=200){window=value;return FALSE;}
    return TRUE;
}
}
extern "C" int __stdcall ProbeInstall(const char* name){
    auto* base=reinterpret_cast<unsigned char*>(GetModuleHandleA(name));
    if(!base)return 0;
    window=GetActiveWindow();
    if(!window)EnumThreadWindows(GetCurrentThreadId(),find_window,0);
    DWORD pid=0;GetWindowThreadProcessId(window,&pid);
    if(pid!=GetCurrentProcessId())return 0;
    auto* dos=reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    if(dos->e_magic!=IMAGE_DOS_SIGNATURE)return 0;
    auto* nt=reinterpret_cast<IMAGE_NT_HEADERS32*>(base+dos->e_lfanew);
    if(nt->Signature!=IMAGE_NT_SIGNATURE||nt->OptionalHeader.Magic!=IMAGE_NT_OPTIONAL_HDR32_MAGIC)return 0;
    HMODULE self=nullptr;
    if(!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_PIN|GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,reinterpret_cast<const char*>(&ProbeInstall),&self))return 0;
    auto* imports=reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(base+nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress);
    FARPROC original[]={GetProcAddress(GetModuleHandleW(L"XInput1_4.dll"),"XInputGetState"),GetProcAddress(GetModuleHandleW(L"XInput1_4.dll"),"XInputSetState"),GetProcAddress(GetModuleHandleW(L"user32.dll"),"GetForegroundWindow")};
    FARPROC replacement[]={reinterpret_cast<FARPROC>(get_state),reinterpret_cast<FARPROC>(set_state),reinterpret_cast<FARPROC>(get_foreground)};
    int changed=0;
    for(;imports->Name;++imports){
        auto* slot=reinterpret_cast<DWORD*>(base+imports->FirstThunk);
        for(;*slot;++slot)for(int i=0;i<3;++i)if(*slot==reinterpret_cast<DWORD>(original[i])){
            DWORD previous=0,ignored=0;
            if(!VirtualProtect(slot,sizeof(*slot),PAGE_READWRITE,&previous))return 0;
            *slot=reinterpret_cast<DWORD>(replacement[i]);
            if(!VirtualProtect(slot,sizeof(*slot),previous,&ignored))return 0;
            ++changed;
        }
    }
    return changed;
}
extern "C" int __stdcall ProbeConfigure(int index,int buttons,int lx,int ly,int triggers,int active){
    if(index<0||index>4||lx<-32768||lx>32767||ly<-32768||ly>32767||triggers<0||triggers>65535)return 0;
    connected=index<4;port=DWORD(index);foreground=active!=0;pad={};
    pad.wButtons=WORD(buttons);pad.sThumbLX=SHORT(lx);pad.sThumbLY=SHORT(ly);
    pad.bLeftTrigger=BYTE(triggers);pad.bRightTrigger=BYTE(triggers>>8);return 1;
}
extern "C" int __stdcall ProbeMotor(int side){return side?right:left;}
extern "C" int __stdcall ProbeReset(){
    return PostMessageW(window,WM_KEYDOWN,VK_F12,0)&&PostMessageW(window,WM_KEYUP,VK_F12,LPARAM(1u<<31));
}
