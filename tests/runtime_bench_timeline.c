#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#define CHECK(x) do {if(!(x)){fprintf(stderr,"check failed: %s (line %d)\n",#x,__LINE__);return 1;}} while(0)
typedef int (__stdcall *Mode)(int);
typedef int (__stdcall *Step)(void);
typedef int (__stdcall *Dump)(const char*);
int main(int argc,char**argv){
    HMODULE module;Mode reset,stage;Step begin,logic,end;Dump timeline,frames;
    FILE* file;char buffer[512],timing[1024],measured[1024];
    int s;unsigned frame;long long start[2],middle[2],finish[2],frequency[2];LARGE_INTEGER clock;
    CHECK(argc==3);module=LoadLibraryA(argv[1]);CHECK(module);
    reset=(Mode)GetProcAddress(module,"BenchReset");stage=(Mode)GetProcAddress(module,"BenchStage");
    begin=(Step)GetProcAddress(module,"BenchBegin");logic=(Step)GetProcAddress(module,"BenchLogic");end=(Step)GetProcAddress(module,"BenchEnd");
    timeline=(Dump)GetProcAddress(module,"BenchWriteTimeline");frames=(Dump)GetProcAddress(module,"BenchWrite");
    CHECK(reset&&stage&&begin&&logic&&end&&timeline&&frames);
    snprintf(timing,sizeof(timing),"%s/timeline.csv",argv[2]);snprintf(measured,sizeof(measured),"%s/frames.csv",argv[2]);
    CHECK(timeline(timing)==0);CHECK(GetFileAttributesA(timing)==INVALID_FILE_ATTRIBUTES);
    CHECK(reset(1)==1&&logic()==0&&stage(17)==1&&begin()==1);
    CHECK(timeline(timing)==0&&GetFileAttributesA(timing)==INVALID_FILE_ATTRIBUTES);
    Sleep(2);CHECK(logic()==1);Sleep(2);CHECK(end()==1);
    CHECK(stage(18)==1&&begin()==1&&logic()==1&&end()==1);
    CHECK(timeline(NULL)==0&&timeline(timing)==2&&frames(measured)==2);
    CHECK(fopen_s(&file,timing,"rb")==0);
    CHECK(fgets(buffer,sizeof(buffer),file)&&strcmp(buffer,"stage,frame,start_qpc,logic_qpc,end_qpc,qpc_frequency\n")==0);
    for(int i=0;i<2;++i){
        CHECK(fgets(buffer,sizeof(buffer),file));
        CHECK(sscanf_s(buffer,"%d,%u,%lld,%lld,%lld,%lld",&s,&frame,&start[i],&middle[i],&finish[i],&frequency[i])==6);
        CHECK(s==17+i&&frame==(unsigned)i&&start[i]<=middle[i]&&middle[i]<=finish[i]&&frequency[i]>0);
    }
    CHECK(!fgets(buffer,sizeof(buffer),file));fclose(file);
    CHECK(QueryPerformanceFrequency(&clock)&&frequency[0]==clock.QuadPart&&frequency[1]==clock.QuadPart&&finish[0]<=start[1]);
    CHECK(fopen_s(&file,measured,"rb")==0&&fgets(buffer,sizeof(buffer),file));
    for(int i=0;i<2;++i){double logic_ms,graphics_ms;CHECK(fgets(buffer,sizeof(buffer),file));
        CHECK(sscanf_s(buffer,"%d,%u,%lf,%lf",&s,&frame,&logic_ms,&graphics_ms)==4);
        CHECK(fabs(logic_ms-(middle[i]-start[i])*1000.0/frequency[i])<=0.000001);
        CHECK(fabs(graphics_ms-(finish[i]-middle[i])*1000.0/frequency[i])<=0.000001);
    }
    fclose(file);FreeLibrary(module);puts("Absolute-QPC timeline, invalid states and measured-duration cross-check: PASS");return 0;
}
