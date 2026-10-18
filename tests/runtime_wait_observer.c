/* Diagnostic only: retain the original wait arguments/result, timer and GC policy. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <intrin.h>
#include <string.h>

typedef DWORD (WINAPI *WaitFn)(DWORD,const HANDLE*,BOOL,DWORD,DWORD);
static WaitFn original;
static void** slot;
static DWORD owner;
static LARGE_INTEGER frequency;
static LONGLONG elapsed,maximum;
static unsigned calls,timeouts,messages;

static DWORD WINAPI observe(DWORD count,const HANDLE* handles,BOOL all,DWORD milliseconds,DWORD mask) {
    LARGE_INTEGER before,after;DWORD result;LONGLONG ticks;
    if(GetCurrentThreadId()!=owner || count || all || milliseconds!=1 || _ReturnAddress()!=(void*)0x10005002)
        return original(count,handles,all,milliseconds,mask);
    QueryPerformanceCounter(&before);
    result=original(count,handles,all,milliseconds,mask);
    QueryPerformanceCounter(&after);
    ticks=after.QuadPart-before.QuadPart;elapsed+=ticks;if(ticks>maximum)maximum=ticks;
    ++calls;if(result==WAIT_TIMEOUT)++timeouts;else if(result==WAIT_OBJECT_0)++messages;
    return result;
}
int __stdcall WaitObserveStart(void) {
    HMODULE module=GetModuleHandleA("RGSS104E.dll");void** candidate;DWORD protection,ignored;
    if(slot || module!=(HMODULE)0x10000000)return -1;
    if(memcmp((char*)module+0x4ffc,"\xff\x15\x70\x63\x12\x10\xeb\x15",8))return -2;
    candidate=(void**)((char*)module+0x126370);
    original=(WaitFn)GetProcAddress(GetModuleHandleA("user32.dll"),"MsgWaitForMultipleObjects");
    if(!original || *candidate!=(void*)original)return -3;
    if(!QueryPerformanceFrequency(&frequency) || frequency.QuadPart<=0)return -4;
    if(!VirtualProtect(candidate,sizeof(void*),PAGE_READWRITE,&protection))return -5;
    owner=GetCurrentThreadId();slot=candidate;InterlockedExchangePointer(slot,(void*)observe);
    if(!VirtualProtect(slot,sizeof(void*),protection,&ignored)){
        InterlockedExchangePointer(slot,(void*)original);slot=NULL;return -6;
    }
    return 1;
}
int __stdcall WaitObserveBegin(void) {
    if(!slot || GetCurrentThreadId()!=owner)return 0;
    elapsed=maximum=0;calls=timeouts=messages=0;return 1;
}
int __stdcall WaitObserveRead(double* output) {
    if(!output || !slot || GetCurrentThreadId()!=owner)return 0;
    output[0]=elapsed*1000.0/frequency.QuadPart;output[1]=maximum*1000.0/frequency.QuadPart;
    output[2]=calls;output[3]=timeouts;output[4]=messages;return 1;
}
int __stdcall WaitObserveStop(void) {
    DWORD protection,ignored;
    if(!slot)return 1;
    if(GetCurrentThreadId()!=owner || *slot!=(void*)observe)return -1;
    if(!VirtualProtect(slot,sizeof(void*),PAGE_READWRITE,&protection))return -2;
    InterlockedExchangePointer(slot,(void*)original);
    if(!VirtualProtect(slot,sizeof(void*),protection,&ignored))return -3;
    slot=NULL;return 1;
}
