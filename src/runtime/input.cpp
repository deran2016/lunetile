#include <windows.h>
#include <imm.h>
#include "graphics.h"
#include "refresh_clock.h"
#include "ui_input.h"
#include "browser.h"
#include "controls_state.h"
#include <Xinput.h>
#include <array>
#include <cmath>
#include <ruby.h>

namespace {
HWND game_window=nullptr;
bool down[256]{},pressed[256]{};
bool browser_blocked=false,suppressed[256]{};
bool suppress_return=false;
bool reset_requested=false;
lunetile_controls::Binding bindings[30];
lunetile_controls::Rumble vibration;
int pad_index=-1,captured_key=0;
unsigned previous_pad=0,captured_pad=0,pad_suppressed=0;
bool pad_device=false,stick_suppressed=false,previous_stick=false;
ULONGLONG next_pad_scan=0;
constexpr UINT_PTR rumble_timer_id=0x4c554e54;
void stop_rumble(){
    if(game_window)KillTimer(game_window,rumble_timer_id);
    if(vibration.until&&pad_index>=0){XINPUT_VIBRATION value{};XInputSetState(pad_index,&value);}
    vibration={};
}
void CALLBACK rumble_timer(HWND,UINT,UINT_PTR,DWORD){
    if(vibration.until&&GetTickCount64()>=vibration.until)stop_rumble();
}
struct Button{bool held=false,trigger=false,repeat=false;unsigned int duration=0;};
Button buttons[30];
bool key(int code){bool physical=(GetAsyncKeyState(code)&0x8000)!=0;if(suppressed[code]){if(!physical&&!down[code])suppressed[code]=false;return false;}return down[code]||physical;}
VALUE update(VALUE){
    bool blocked=browser_input_blocked();
    if(blocked!=browser_blocked){
        browser_blocked=blocked;input_browser_release();
    }
    HWND foreground=GetForegroundWindow();
    bool active=foreground==game_window&&!blocked;
    ULONGLONG now=GetTickCount64();
    XINPUT_STATE pad{};
    if(active&&pad_index<0&&now>=next_pad_scan){
        next_pad_scan=now+1000;
        for(DWORD i=0;i<XUSER_MAX_COUNT;++i)if(XInputGetState(i,&pad)==ERROR_SUCCESS){pad_index=int(i);break;}
    }
    bool physical=pad_index>=0&&XInputGetState(pad_index,&pad)==ERROR_SUCCESS;
    bool connected=active&&physical;
    if(!physical&&pad_index>=0){stop_rumble();pad_index=-1;previous_pad=0;}
    unsigned raw=physical?pad.Gamepad.wButtons:0;
    if(physical&&pad.Gamepad.bLeftTrigger>XINPUT_GAMEPAD_TRIGGER_THRESHOLD)raw|=0x10000;
    if(physical&&pad.Gamepad.bRightTrigger>XINPUT_GAMEPAD_TRIGGER_THRESHOLD)raw|=0x20000;
    if(!active)stick_suppressed=true;
    unsigned flags=lunetile_controls::filter_pad(raw,active,pad_suppressed);
    captured_key=0;captured_pad=flags&~previous_pad;
    if(captured_pad)captured_pad&=0u-captured_pad;
    if(active)for(int k=8;k<256;++k)if(pressed[k]&&lunetile_controls::valid_key(k)&&!(k==VK_RETURN&&suppress_return)){captured_key=k;break;}
    if(captured_key)pad_device=false;
    else if(captured_pad)pad_device=true;
    previous_pad=raw;
    if(vibration.expire(now,connected&&!blocked)){KillTimer(game_window,rumble_timer_id);XINPUT_VIBRATION value{};if(pad_index>=0)XInputSetState(pad_index,&value);}
    auto any=[&](std::initializer_list<int> keys){bool value=false;for(int k:keys)value=value||key(k)||pressed[k];return active&&value;};
    bool state[30]{};
    for(int id:lunetile_controls::actions){
        auto& mapping=bindings[id];
        state[id]=(flags&mapping.pad)!=0;
        for(int j=0;j<mapping.count;++j){int k=mapping.keys[j];if(k!=VK_RETURN||!suppress_return)state[id]=state[id]||(active&&(key(k)||pressed[k]));}
    }
    bool stick=physical&&(std::abs(int(pad.Gamepad.sThumbLX))>16000||std::abs(int(pad.Gamepad.sThumbLY))>16000);
    if(lunetile_controls::filter_stick(stick,active,stick_suppressed)){
        state[2]=state[2]||pad.Gamepad.sThumbLY<-16000;state[8]=state[8]||pad.Gamepad.sThumbLY>16000;
        state[4]=state[4]||pad.Gamepad.sThumbLX<-16000;state[6]=state[6]||pad.Gamepad.sThumbLX>16000;
        if(!captured_key&&!previous_stick)pad_device=true;
    }
    previous_stick=stick;
    state[21]=any({VK_SHIFT});state[22]=any({VK_CONTROL});state[23]=any({VK_MENU});
    for(int i=25;i<=29;++i)state[i]=any({VK_F5+i-25});
    for(int i=0;i<30;++i){auto& b=buttons[i];b.trigger=state[i]&&!b.held;b.held=state[i];b.duration=state[i]?b.duration+1:0;b.repeat=b.trigger||(rgss_refresh::repeat_due(b.duration,graphics_time_scale()));}
    for(auto& value:pressed)value=false;
    ui_input_update();
    return Qnil;
}
int button(VALUE value){
#ifdef RGSS_VXA
    if(SYMBOL_P(value)){
        VALUE input=rb_const_get(rb_cObject,rb_intern("Input"));
        ID name=SYM2ID(value);
        if(!rb_const_defined_at(input,name))rb_raise(rb_eArgError,"Unknown input button");
        value=rb_const_get_at(input,name);
    }
#endif
    int id=NUM2INT(value);if(id<0||id>=30)rb_raise(rb_eArgError,"Unknown input button");return id;
}
VALUE press(VALUE,VALUE value){return buttons[button(value)].held?Qtrue:Qfalse;}
VALUE trigger(VALUE,VALUE value){return buttons[button(value)].trigger?Qtrue:Qfalse;}
VALUE repeat(VALUE,VALUE value){return buttons[button(value)].repeat?Qtrue:Qfalse;}
VALUE dir4(VALUE){bool d=buttons[2].held,u=buttons[8].held,l=buttons[4].held,r=buttons[6].held;if(d&&u)d=u=false;if(l&&r)l=r=false;return INT2NUM(d?2:l?4:r?6:u?8:0);}
VALUE dir8(VALUE){int x=(buttons[6].held?1:0)-(buttons[4].held?1:0),y=(buttons[2].held?1:0)-(buttons[8].held?1:0);return INT2NUM(!x&&!y?0:5+x-y*3);}
VALUE configure(VALUE,VALUE rows){
    Check_Type(rows,T_ARRAY);
    if(RARRAY_LEN(rows)!=12)rb_raise(rb_eArgError,"Expected all 12 control bindings");
    lunetile_controls::Binding next[30]{};bool seen[30]{};
    for(long i=0;i<12;++i){
        VALUE row=rb_ary_entry(rows,i);Check_Type(row,T_ARRAY);
        if(RARRAY_LEN(row)!=3)rb_raise(rb_eArgError,"Invalid control binding");
        int id=NUM2INT(rb_ary_entry(row,0));
        if(!lunetile_controls::action(id)||seen[id])rb_raise(rb_eArgError,"Invalid or repeated control action");
        seen[id]=true;VALUE keys=rb_ary_entry(row,1);Check_Type(keys,T_ARRAY);
        long count=RARRAY_LEN(keys);if(count>4)rb_raise(rb_eArgError,"At most four keyboard keys per action");
        next[id].count=int(count);
        for(long j=0;j<count;++j){int k=NUM2INT(rb_ary_entry(keys,j));if(!lunetile_controls::valid_key(k))rb_raise(rb_eArgError,"Reserved or invalid keyboard key");next[id].keys[j]=k;}
        unsigned p=NUM2UINT(rb_ary_entry(row,2));if(!lunetile_controls::valid_pad(p))rb_raise(rb_eArgError,"Invalid gamepad button");next[id].pad=p;
    }
    for(int id:lunetile_controls::actions){bindings[id]=next[id];buttons[id]=Button{};}
    return Qnil;
}
VALUE capture(VALUE){return rb_ary_new_from_args(2,captured_key?INT2NUM(captured_key):Qnil,captured_pad?UINT2NUM(captured_pad):Qnil);}
VALUE device(VALUE){return ID2SYM(rb_intern(pad_device?"gamepad":"keyboard"));}
VALUE pad_connected(VALUE){return pad_index>=0?Qtrue:Qfalse;}
VALUE rumble(VALUE,VALUE left,VALUE right,VALUE duration){
    double l=NUM2DBL(left),r=NUM2DBL(right);int ms=NUM2INT(duration);
    if(!std::isfinite(l)||!std::isfinite(r)||l<0||l>1||r<0||r>1||ms<0||ms>5000)rb_raise(rb_eArgError,"Rumble requires strengths 0..1 and duration 0..5000ms");
    if(!ms||(!l&&!r)){stop_rumble();return Qtrue;}
    if(pad_index<0||GetForegroundWindow()!=game_window||browser_input_blocked())return Qfalse;
    XINPUT_VIBRATION value{static_cast<WORD>(l*65535),static_cast<WORD>(r*65535)};
    if(XInputSetState(pad_index,&value)!=ERROR_SUCCESS){stop_rumble();return Qfalse;}
    vibration.start(value.wLeftMotorSpeed,value.wRightMotorSpeed,GetTickCount64(),ms);
    if(!SetTimer(game_window,rumble_timer_id,UINT(ms),rumble_timer)){stop_rumble();return Qfalse;}
    return Qtrue;
}
}
void input_attach(HWND window){game_window=window;}
bool input_pretranslate(const MSG& message){
    if(message.hwnd!=game_window)return false;
    bool down_event=message.message==WM_KEYDOWN||message.message==WM_SYSKEYDOWN;
    bool up_event=message.message==WM_KEYUP||message.message==WM_SYSKEYUP;
    if(!down_event&&!up_event)return false;
    UINT code=UINT(message.wParam);
    if(down_event&&code==VK_PROCESSKEY){UINT original=ImmGetVirtualKey(game_window);if(original)code=original;}
    if(code>=256)return false;
    if(up_event||!(message.lParam&(1L<<30)))suppressed[code]=false;
    // Discard held browser keys before TranslateMessage can turn them into game text.
    return down_event&&suppressed[code];
}
void input_browser_release(){
    stop_rumble();pad_suppressed|=previous_pad;stick_suppressed=true;
    for(auto& b:buttons)b=Button{};
    for(int i=0;i<256;++i){if(i!=VK_F12)down[i]=pressed[i]=false;suppressed[i]=(GetAsyncKeyState(i)&0x8000)!=0;}
    ui_input_reset();
}
bool input_take_reset(){bool requested=reset_requested;reset_requested=false;return requested;}
void input_reset(){stop_rumble();pad_suppressed|=previous_pad;stick_suppressed=true;captured_key=0;captured_pad=0;ui_input_reset();for(auto& button:buttons)button=Button{};bool f12=down[VK_F12];for(auto& value:down)value=false;down[VK_F12]=f12;for(auto& value:pressed)value=false;for(auto& value:suppressed)value=false;browser_blocked=false;reset_requested=false;suppress_return=false;}
void input_message(UINT message,WPARAM keycode,LPARAM flags){
    if(message==WM_KEYDOWN&&keycode==VK_F12&&!down[VK_F12])reset_requested=true;
    if(message==WM_SYSKEYDOWN&&keycode==VK_RETURN){suppress_return=true;down[VK_RETURN]=pressed[VK_RETURN]=false;}
    else if((message==WM_KEYDOWN||message==WM_SYSKEYDOWN)&&keycode<256){if(!(flags&(1L<<30)))suppressed[keycode]=false;if(!down[keycode])pressed[keycode]=true;down[keycode]=true;}
    else if((message==WM_KEYUP||message==WM_SYSKEYUP)&&keycode<256){down[keycode]=false;suppressed[keycode]=false;if(keycode==VK_RETURN)suppress_return=false;}
    else if(message==WM_KILLFOCUS){stop_rumble();pad_suppressed|=previous_pad;stick_suppressed=true;for(auto& value:down)value=false;for(auto& value:pressed)value=false;suppress_return=false;reset_requested=false;}
}
void init_input(){
    init_ui_input();
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
    VALUE controls=rb_define_module_under(rb_define_module("Lunetile"),"Controls");
    rb_define_singleton_method(controls,"__configure",RUBY_METHOD_FUNC(configure),1);
    rb_define_singleton_method(controls,"capture",RUBY_METHOD_FUNC(capture),0);
    rb_define_singleton_method(controls,"device",RUBY_METHOD_FUNC(device),0);
    rb_define_singleton_method(controls,"connected?",RUBY_METHOD_FUNC(pad_connected),0);
    rb_define_singleton_method(controls,"__rumble",RUBY_METHOD_FUNC(rumble),3);
}
