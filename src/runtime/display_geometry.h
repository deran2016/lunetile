#pragma once
#include <algorithm>

namespace rgss_display {
struct Fit { float x, y, width, height; };
inline Fit fit(float width, float height, float output_width, float output_height) {
    float scale = std::min(output_width / width, output_height / height);
    return {(output_width-width*scale)/2, (output_height-height*scale)/2, width*scale, height*scale};
}
inline bool valid(int width, int height) {
    // Bound three RGBA surfaces in the 32-bit process, including transactional resize copies.
    return width > 0 && height > 0 && width <= 4096 && height <= 4096 &&
        static_cast<long long>(width)*height <= 8294400;
}
inline bool locate(int width,int height,int output_width,int output_height,int px,int py,int& x,int& y) {
    if(width<=0||height<=0||output_width<=0||output_height<=0)return false;
    auto area=fit(float(width),float(height),float(output_width),float(output_height));
    if(px<area.x||py<area.y||px>=area.x+area.width||py>=area.y+area.height)return false;
    x=int((px-area.x)*width/area.width);y=int((py-area.y)*height/area.height);return true;
}
}
