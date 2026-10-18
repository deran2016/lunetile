#pragma once
#include <cstdint>

namespace rgss_refresh {
inline bool repeat_due(unsigned duration, unsigned scale) {
    unsigned first=16*scale+1;
    return duration>=first && (duration-first)%(4*scale)==0;
}
struct Clock {
    int logic=40, output=40, phase=0;
    std::uint64_t due=0, presented=0, dropped=0, late=0;
    bool high() const { return logic==120; }
    void reset() { phase=0; }
    bool next() {
        phase+=output;
        if(phase<logic)return false;
        phase-=logic;++due;return true;
    }
    static bool valid(int rate) { return rate==40||rate==60||rate==120; }
};
}
