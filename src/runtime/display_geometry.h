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
}
