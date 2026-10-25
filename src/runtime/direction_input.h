#pragma once
#include <array>
#include <cstdint>

struct DirectionInput {
    std::array<bool,4> held{};
    std::array<std::uint64_t,4> order{};
    std::uint64_t serial=0;
    int pending=0,trigger=0;

    void press(int direction) {
        if (!direction) return;
        auto index=direction/2-1;
        if (held[index]) return;
        held[index]=true;order[index]=++serial;pending=direction;
    }
    void release(int direction) {
        if (direction) held[direction/2-1]=false;
    }
    int direction4() const {
        int result=0;std::uint64_t latest=0;
        for (int i=0;i<4;++i) if (held[i]&&order[i]>latest) {
            latest=order[i];result=(i+1)*2;
        }
        return result;
    }
    void update() { trigger=pending;pending=0; }
    void clear_pending() { pending=trigger=0; }
    void reset() { *this={}; }
};
