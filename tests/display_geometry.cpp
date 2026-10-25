#include "display_geometry.h"
#include "refresh_clock.h"
#include <cstdlib>
#include <iostream>

int main() {
    int x=0,y=0;
    if(!rgss_display::locate(1280,720,1920,1200,960,600,x,y)||x!=640||y!=360)return EXIT_FAILURE;
    if(rgss_display::locate(1280,720,1920,1200,960,20,x,y))return EXIT_FAILURE;
    if(!rgss_display::locate(1280,720,2560,1440,1920,1080,x,y)||x!=960||y!=540)return EXIT_FAILURE;
    if(rgss_display::locate(1280,720,0,0,0,0,x,y))return EXIT_FAILURE;
    for (auto output : {1920,2560,3840}) {
        auto fit=rgss_display::fit(1280,720,static_cast<float>(output),output*9.0f/16);
        if(fit.x!=0 || fit.y!=0 || fit.width!=output || fit.height!=output*9.0f/16)return EXIT_FAILURE;
    }
    auto fit=rgss_display::fit(1280,720,1920,1200);
    if(fit.x!=0 || fit.y!=60 || fit.width!=1920 || fit.height!=1080)return EXIT_FAILURE;
    fit=rgss_display::fit(640,480,1920,1080);
    if(fit.x!=240 || fit.y!=0 || fit.width!=1440 || fit.height!=1080)return EXIT_FAILURE;
    if(rgss_display::valid(0,720) || rgss_display::valid(-1,720) || rgss_display::valid(4096,4096) || !rgss_display::valid(3840,2160))return EXIT_FAILURE;
    if(!rgss_refresh::repeat_due(17,1)||!rgss_refresh::repeat_due(49,3)||!rgss_refresh::repeat_due(61,3)||rgss_refresh::repeat_due(50,3))return EXIT_FAILURE;
    for(int rate : {40,60,120}){
        rgss_refresh::Clock clock;clock.logic=120;clock.output=rate;
        for(int tick=0;tick<120;++tick)clock.next();
        if(clock.due!=static_cast<unsigned>(rate))return EXIT_FAILURE;
        clock.output=60;clock.reset();auto before=clock.due;
        for(int tick=0;tick<120;++tick)clock.next();
        if(clock.due-before!=60)return EXIT_FAILURE;
        clock.reset();if(clock.next())return EXIT_FAILURE;
    }
    if(rgss_refresh::Clock::valid(90)||rgss_refresh::Clock::valid(0))return EXIT_FAILURE;
    rgss_refresh::Clock busy;busy.logic=120;busy.output=120;
    for(int tick=0;tick<120;++tick){if(busy.next()){if(tick%2)++busy.dropped;else ++busy.presented;}}
    if(busy.due!=120||busy.presented!=60||busy.dropped!=60)return EXIT_FAILURE;
    std::cout << "FHD/QHD/4K geometry, refresh cadence, dropped output and input repeat PASS\n";
}
