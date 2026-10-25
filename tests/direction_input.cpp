#include "direction_input.h"
#include <cassert>
#include <cstdio>

int main() {
    DirectionInput input;
    for (int direction:{8,6,2,4}) {input.press(direction);input.release(direction);}
    input.update();assert(input.trigger==4);assert(input.direction4()==0);
    input.update();assert(input.trigger==0);
    input.press(8);input.press(6);input.update();
    assert(input.trigger==6&&input.direction4()==6);
    input.press(8);input.update(); // Windows autorepeat must not change priority.
    assert(input.trigger==0&&input.direction4()==6);
    input.release(6);assert(input.direction4()==8);
    input.press(2);input.update();assert(input.trigger==2&&input.direction4()==2);
    input.release(2);input.release(8);input.press(4);input.clear_pending();input.update();
    assert(input.trigger==0&&input.direction4()==4);
    input.reset();input.update();assert(input.trigger==0&&input.direction4()==0);
    input.press(0);input.release(0);input.update();assert(input.trigger==0);
    std::puts("direction input PASS: ordered taps, overlap, opposites, repeat, text transition, focus reset");
}
