#include "display_geometry.h"
#include <cstdlib>
#include <iostream>

int main() {
    for (auto output : {1920,2560,3840}) {
        auto fit=rgss_display::fit(1280,720,static_cast<float>(output),output*9.0f/16);
        if(fit.x!=0 || fit.y!=0 || fit.width!=output || fit.height!=output*9.0f/16)return EXIT_FAILURE;
    }
    auto fit=rgss_display::fit(1280,720,1920,1200);
    if(fit.x!=0 || fit.y!=60 || fit.width!=1920 || fit.height!=1080)return EXIT_FAILURE;
    fit=rgss_display::fit(640,480,1920,1080);
    if(fit.x!=240 || fit.y!=0 || fit.width!=1440 || fit.height!=1080)return EXIT_FAILURE;
    if(rgss_display::valid(0,720) || rgss_display::valid(-1,720) || rgss_display::valid(4096,4096) || !rgss_display::valid(3840,2160))return EXIT_FAILURE;
    std::cout << "FHD/QHD/4K, letterbox and legacy 4:3 geometry PASS\n";
}
