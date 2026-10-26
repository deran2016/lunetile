#pragma once
#include <cstdint>

namespace lunetile_controls {
inline constexpr int actions[] = {2,4,6,8,11,12,13,14,15,16,17,18};
inline constexpr unsigned pad_bits = 0x3f3ff;
struct Binding { int keys[4]{}; int count=0; unsigned pad=0; };
inline bool action(int id) {
    for(int value:actions)if(value==id)return true;
    return false;
}
inline bool valid_key(int key) { return key>=8&&key<256&&key!=0x7b&&key!=0xe5; }
inline bool valid_pad(unsigned value) { return !value||(!(value&(value-1))&&!(value&~pad_bits)); }
inline unsigned filter_pad(unsigned raw,bool active,unsigned& suppressed) {
    if(!active)suppressed|=raw;
    suppressed&=raw;
    return active?raw&~suppressed:0;
}
inline bool filter_stick(bool held,bool active,bool& suppressed) {
    if(!active&&held)suppressed=true;
    if(!held)suppressed=false;
    return active&&held&&!suppressed;
}
struct Rumble {
    unsigned short left=0,right=0;
    std::uint64_t until=0;
    void start(unsigned short l,unsigned short r,std::uint64_t now,unsigned duration) {
        left=l;right=r;until=duration&&(l||r)?now+duration:0;
        if(!until)left=right=0;
    }
    bool expire(std::uint64_t now,bool active) {
        if(until&&(!active||now>=until)){left=right=0;until=0;return true;}
        return false;
    }
};
}
