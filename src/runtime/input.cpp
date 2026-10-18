#include <windows.h>
#include "graphics.h"
#include "refresh_clock.h"
#include <Xinput.h>
#include <array>
#include <ruby.h>

namespace {
HWND game_window=nullptr;
bool down[256]{},pressed[256]{};
bool suppress_return=false;
bool reset_requested=false;
struct Button{bool held=false,trigger=false,repeat=false;unsigned int duration=0;};
Button buttons[30];
bool key(int code){return down[code]||((GetAsyncKeyState(code)&0x8000)!=0);}
VALUE update(VALUE){
    HWND foreground=GetForegroundWindow();
    bool active=foreground==game_window;
    XINPUT_STATE pad{};bool connected=active&&XInputGetState(0,&pad)==ERROR_SUCCESS;
    WORD flags=connected?pad.Gamepad.wButtons:0;
    auto any=[&](std::initializer_list<int> keys){bool value=false;for(int k:keys)value=value||key(k)||pressed[k];return active&&value;};
    bool state[30]{};
    state[2]=any({VK_DOWN})||(flags&XINPUT_GAMEPAD_DPAD_DOWN)||(connected&&pad.Gamepad.sThumbLY<-16000);
    state[4]=any({VK_LEFT})||(flags&XINPUT_GAMEPAD_DPAD_LEFT)||(connected&&pad.Gamepad.sThumbLX<-16000);
    state[6]=any({VK_RIGHT})||(flags&XINPUT_GAMEPAD_DPAD_RIGHT)||(connected&&pad.Gamepad.sThumbLX>16000);
    state[8]=any({VK_UP})||(flags&XINPUT_GAMEPAD_DPAD_UP)||(connected&&pad.Gamepad.sThumbLY>16000);
    state[11]=any({VK_SHIFT})||(flags&XINPUT_GAMEPAD_X);
    state[12]=any({VK_ESCAPE,'X',VK_NUMPAD0})||(flags&XINPUT_GAMEPAD_B);
    state[13]=any({VK_SPACE,'Z'})||(!suppress_return&&any({VK_RETURN}))||(flags&XINPUT_GAMEPAD_A);
    state[14]=any({'A'})||(flags&XINPUT_GAMEPAD_Y);
    state[15]=any({'S'});state[16]=any({'D'});
    state[17]=any({'Q',VK_PRIOR})||(flags&XINPUT_GAMEPAD_LEFT_SHOULDER);
    state[18]=any({'W',VK_NEXT})||(flags&XINPUT_GAMEPAD_RIGHT_SHOULDER);
    state[21]=any({VK_SHIFT});state[22]=any({VK_CONTROL});state[23]=any({VK_MENU});
    for(int i=25;i<=29;++i)state[i]=any({VK_F5+i-25});
    for(int i=0;i<30;++i){auto& b=buttons[i];b.trigger=state[i]&&!b.held;b.held=state[i];b.duration=state[i]?b.duration+1:0;b.repeat=b.trigger||(rgss_refresh::repeat_due(b.duration,graphics_time_scale()));}
    for(auto& value:pressed)value=false;
    return Qnil;
}
int button(VALUE value){int id=NUM2INT(value);if(id<0||id>=30)rb_raise(rb_eArgError,"Unknown input button");return id;}
VALUE press(VALUE,VALUE value){return buttons[button(value)].held?Qtrue:Qfalse;}
VALUE trigger(VALUE,VALUE value){return buttons[button(value)].trigger?Qtrue:Qfalse;}
VALUE repeat(VALUE,VALUE value){return buttons[button(value)].repeat?Qtrue:Qfalse;}
VALUE dir4(VALUE){bool d=buttons[2].held,u=buttons[8].held,l=buttons[4].held,r=buttons[6].held;if(d&&u)d=u=false;if(l&&r)l=r=false;return INT2NUM(d?2:l?4:r?6:u?8:0);}
VALUE dir8(VALUE){int x=(buttons[6].held?1:0)-(buttons[4].held?1:0),y=(buttons[2].held?1:0)-(buttons[8].held?1:0);return INT2NUM(!x&&!y?0:5+x-y*3);}
}
void input_attach(HWND window){game_window=window;}
bool input_take_reset(){bool requested=reset_requested;reset_requested=false;return requested;}
void input_reset(){for(auto& button:buttons)button=Button{};bool f12=down[VK_F12];for(auto& value:down)value=false;down[VK_F12]=f12;for(auto& value:pressed)value=false;reset_requested=false;suppress_return=false;}
void input_message(UINT message,WPARAM keycode){
    if(message==WM_KEYDOWN&&keycode==VK_F12&&!down[VK_F12])reset_requested=true;
    if(message==WM_SYSKEYDOWN&&keycode==VK_RETURN){suppress_return=true;down[VK_RETURN]=pressed[VK_RETURN]=false;}
    else if((message==WM_KEYDOWN||message==WM_SYSKEYDOWN)&&keycode<256){if(!down[keycode])pressed[keycode]=true;down[keycode]=true;}
    else if((message==WM_KEYUP||message==WM_SYSKEYUP)&&keycode<256){down[keycode]=false;if(keycode==VK_RETURN)suppress_return=false;}
    else if(message==WM_KILLFOCUS){for(auto& value:down)value=false;for(auto& value:pressed)value=false;suppress_return=false;reset_requested=false;}
}
void init_input(){
    VALUE input=rb_define_module("Input");
    const char* names[]={"DOWN","LEFT","RIGHT","UP","A","B","C","X","Y","Z","L","R","SHIFT","CTRL","ALT","F5","F6","F7","F8","F9"};
    int ids[]={2,4,6,8,11,12,13,14,15,16,17,18,21,22,23,25,26,27,28,29};
    for(int i=0;i<20;++i)rb_define_const(input,names[i],INT2NUM(ids[i]));
    rb_define_singleton_method(input,"update",RUBY_METHOD_FUNC(update),0);
    rb_define_singleton_method(input,"press?",RUBY_METHOD_FUNC(press),1);
    rb_define_singleton_method(input,"trigger?",RUBY_METHOD_FUNC(trigger),1);
    rb_define_singleton_method(input,"repeat?",RUBY_METHOD_FUNC(repeat),1);
    rb_define_singleton_method(input,"dir4",RUBY_METHOD_FUNC(dir4),0);
    rb_define_singleton_method(input,"dir8",RUBY_METHOD_FUNC(dir8),0);
}
