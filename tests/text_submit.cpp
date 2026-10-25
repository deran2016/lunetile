#include "text_submit.h"
#include <cassert>
#include <cstdio>
int main(){
    TextSubmit s;s.press(false,false,false);s.update(true,false);assert(!s.triggered);s.release();
    s.press(true,true,false);s.update(true,true);assert(!s.triggered);
    s.committed();s.update(true,true);assert(s.triggered);s.update(true,false);assert(!s.triggered);
    s.press(true,false,true);s.update(true,false);assert(!s.triggered);s.release();
    s.press(true,false,false);s.update(true,false);assert(s.triggered);s.cancel();s.update(true,false);assert(!s.triggered);
    s.release();s.press(true,true,false);s.reset();s.update(true,false);assert(!s.triggered);
    std::puts("text submit PASS: opening, composition commit, single delivery, repeat, cancel, focus loss");
}
