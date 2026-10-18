/* Measurement only: no engine addresses, hooks, timer or priority changes. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>

typedef struct {LONGLONG qpc; ULONGLONG thread,process,cycles; DWORD active;} Stamp;
typedef struct {int stage;Stamp start,logic,end;LONGLONG previous;} Row;
static LARGE_INTEGER frequency,epoch;
static Row rows[8192],current;
static unsigned count;
static int detailed,stage,open;
static LONGLONG previous;
static ULONGLONG cpu(int process) {
    FILETIME created,exited,kernel,user;
    BOOL ok=process?GetProcessTimes(GetCurrentProcess(),&created,&exited,&kernel,&user):GetThreadTimes(GetCurrentThread(),&created,&exited,&kernel,&user);
    if(!ok)return 0;
    return (((ULONGLONG)kernel.dwHighDateTime<<32)|kernel.dwLowDateTime)+(((ULONGLONG)user.dwHighDateTime<<32)|user.dwLowDateTime);
}
static Stamp snapshot(void) {
    Stamp value={0};LARGE_INTEGER clock;DWORD pid=0;
    QueryPerformanceCounter(&clock);value.qpc=clock.QuadPart;
    if(detailed){value.thread=cpu(0);value.process=cpu(1);QueryThreadCycleTime(GetCurrentThread(),&value.cycles);}
    GetWindowThreadProcessId(GetForegroundWindow(),&pid);value.active=pid==GetCurrentProcessId();
    return value;
}
int __stdcall BenchReset(int mode) {
    if(mode<0||mode>1||!QueryPerformanceFrequency(&frequency)||frequency.QuadPart<=0)return 0;
    QueryPerformanceCounter(&epoch);detailed=mode;count=0;stage=0;open=0;previous=0;return 1;
}
int __stdcall BenchStage(int value){if(open)return 0;stage=value;previous=0;return 1;}
int __stdcall BenchBegin(void){if(open||count>=8192)return 0;current.stage=stage;current.previous=previous;current.start=snapshot();open=1;return 1;}
int __stdcall BenchLogic(void){if(open!=1)return 0;current.logic=snapshot();open=2;return 1;}
int __stdcall BenchEnd(void){if(open!=2)return 0;current.end=snapshot();rows[count++]=current;previous=current.end.qpc;open=0;return 1;}
DWORD __stdcall BenchClock(void){LARGE_INTEGER now;QueryPerformanceCounter(&now);return (DWORD)((now.QuadPart-epoch.QuadPart)*1000000/frequency.QuadPart);}
int __stdcall BenchWrite(const char* path) {
    FILE* file=NULL;unsigned i;
    if(open||!path||fopen_s(&file,path,"wb"))return 0;
    fputs("stage,frame,logic_wall_ms,graphics_wall_ms,interval_ms,logic_cpu_ms,graphics_cpu_ms,process_cpu_ms,thread_cycles,active_start,active_end\n",file);
    for(i=0;i<count;++i){Row* r=&rows[i];double scale=1000.0/frequency.QuadPart;
        fprintf(file,"%d,%u,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%llu,%lu,%lu\n",r->stage,i,
            (r->logic.qpc-r->start.qpc)*scale,(r->end.qpc-r->logic.qpc)*scale,
            (r->end.qpc-(r->previous?r->previous:r->start.qpc))*scale,
            (r->logic.thread-r->start.thread)/10000.0,(r->end.thread-r->logic.thread)/10000.0,
            (r->end.process-r->start.process)/10000.0,r->end.cycles-r->start.cycles,r->start.active,r->end.active);
    }
    return fclose(file)==0?(int)count:0;
}
/* Absolute QPC stamps join separate ETW records without adding calls to measured frames. */
int __stdcall BenchWriteTimeline(const char* path) {
    FILE* file=NULL;unsigned i;
    if(open||!path||frequency.QuadPart<=0||fopen_s(&file,path,"wb"))return 0;
    fputs("stage,frame,start_qpc,logic_qpc,end_qpc,qpc_frequency\n",file);
    for(i=0;i<count;++i){Row* r=&rows[i];
        if(fprintf(file,"%d,%u,%lld,%lld,%lld,%lld\n",r->stage,i,r->start.qpc,r->logic.qpc,r->end.qpc,frequency.QuadPart)<0){fclose(file);return 0;}
    }
    return fclose(file)==0?(int)count:0;
}
