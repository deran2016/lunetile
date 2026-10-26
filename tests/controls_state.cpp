#include "controls_state.h"
#include <cassert>
#include <iostream>
int main(){
    using namespace lunetile_controls;
    assert(action(13)&&!action(0)&&!action(29));
    assert(valid_key(13)&&valid_key(255)&&!valid_key(123)&&!valid_key(229)&&!valid_key(-1)&&!valid_key(256));
    assert(valid_pad(0)&&valid_pad(0x20000)&&valid_pad(0x1000)&&!valid_pad(3)&&!valid_pad(0x400)&&!valid_pad(0x40000));
    unsigned suppressed=0;
    assert(filter_pad(0x1000,true,suppressed)==0x1000);
    bool blocked=false;
    assert(!filter_stick(true,false,blocked)&&blocked);
    assert(!filter_stick(true,true,blocked));
    assert(!filter_stick(false,true,blocked)&&!blocked);
    assert(filter_stick(true,true,blocked));
    assert(filter_pad(0x1000,false,suppressed)==0);
    assert(filter_pad(0x1000,true,suppressed)==0);
    assert(filter_pad(0,true,suppressed)==0&&!suppressed);
    assert(filter_pad(0x1000,true,suppressed)==0x1000);
    Rumble r;r.start(30000,65535,100,150);
    assert(r.left==30000&&r.right==65535&&!r.expire(249,true));
    assert(r.expire(250,true)&&!r.left&&!r.right&&!r.until);
    assert(!r.expire(251,true));
    r.start(100,200,500,1000);assert(r.expire(501,false)&&!r.left&&!r.right);
    r.start(100,200,500,0);assert(!r.until&&!r.left&&!r.right);
    r.start(0,0,500,500);assert(!r.until);
    std::cout<<"Controls key/pad validation and rumble deadline/focus stop PASS\n";
}
