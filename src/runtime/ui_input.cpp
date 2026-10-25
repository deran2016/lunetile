#include <windows.h>
#include <imm.h>
#include <array>
#include <string>
#include <ruby.h>
#include <ruby/encoding.h>
#include "ui_input.h"
#include "display_geometry.h"
#include "direction_input.h"
#include "text_submit.h"

namespace {
HWND target=nullptr;
std::array<bool,256> held{},pending{},triggered{};
DirectionInput directions;
TextSubmit submit;
int arrow(WPARAM key) {
    switch(key) {case VK_DOWN:return 2;case VK_LEFT:return 4;case VK_RIGHT:return 6;case VK_UP:return 8;default:return 0;}
}
int pending_wheel=0,wheel=0;
bool editing=false,composing=false,ime_enter=false;
bool ime_owned=false;
BOOL saved_open=FALSE;
DWORD saved_conversion=0,saved_sentence=0;
std::wstring committed,composition;
RECT caret{0,0,1,20};
POINT pending_point{},press_point{};
bool pending_position=false,pressed_position=false;
unsigned long key_messages=0,char_messages=0,ime_messages=0;
ULONGLONG last_ime_message=0;
void suspend_ime(){
    if(!ime_owned||!target)return;
    HIMC context=ImmGetContext(target);if(!context)return;
    if(editing){saved_open=ImmGetOpenStatus(context);ImmGetConversionStatus(context,&saved_conversion,&saved_sentence);}
    ImmNotifyIME(context,NI_COMPOSITIONSTR,CPS_CANCEL,0);ImmSetOpenStatus(context,FALSE);ImmReleaseContext(target,context);
}
rgss_display::Fit area(){int w,h;graphics_input_size(w,h);RECT r{};GetClientRect(target,&r);return rgss_display::fit(float(w),float(h),float(r.right),float(r.bottom));}
void place_ime(){
    if(!target)return;
    int w,h;graphics_input_size(w,h);auto a=area();
    POINT p{LONG(a.x+caret.left*a.width/w),LONG(a.y+caret.top*a.height/h)};
    HIMC context=ImmGetContext(target);if(!context)return;
    COMPOSITIONFORM form{CFS_POINT,p,{}};ImmSetCompositionWindow(context,&form);
    CANDIDATEFORM candidate{0,CFS_CANDIDATEPOS,{p.x,p.y+LONG((caret.bottom-caret.top)*a.height/h)},{}};
    ImmSetCandidateWindow(context,&candidate);ImmReleaseContext(target,context);
}
int code(VALUE value){
    if(RB_INTEGER_TYPE_P(value)){int v=NUM2INT(value);if(v<0||v>255)rb_raise(rb_eArgError,"Key must be 0..255");return v;}
    VALUE s=SYMBOL_P(value)?rb_sym2str(value):value;StringValue(s);std::string name(RSTRING_PTR(s),RSTRING_LEN(s));
    if(name.size()==1){char c=name[0];if(c>='a'&&c<='z')c-=32;if((c>='A'&&c<='Z')||(c>='0'&&c<='9'))return c;}
    const char* names[]={"enter","escape","space","tab","backspace","delete","left","right","home","end","shift","up","down","left_mouse","right_mouse"};
    int keys[]={VK_RETURN,VK_ESCAPE,VK_SPACE,VK_TAB,VK_BACK,VK_DELETE,VK_LEFT,VK_RIGHT,VK_HOME,VK_END,VK_SHIFT,VK_UP,VK_DOWN,VK_LBUTTON,VK_RBUTTON};
    for(int i=0;i<15;++i)if(name==names[i])return keys[i];
    rb_raise(rb_eArgError,"Unknown UI key");
}
VALUE key_trigger(VALUE,VALUE key){
    int k=code(key);
    // Korean IME may commit/end composition before forwarding its confirming key.
    if(editing&&last_ime_message&&GetTickCount64()-last_ime_message<75&&(k==VK_RETURN||k==VK_BACK||k==VK_DELETE))return Qfalse;
    return triggered[k]?Qtrue:Qfalse;
}
VALUE key_press(VALUE,VALUE key){return held[code(key)]?Qtrue:Qfalse;}
VALUE direction4(VALUE){return INT2NUM(directions.direction4());}
VALUE direction_trigger(VALUE){return INT2NUM(directions.trigger);}
VALUE mouse_position(VALUE){
    if(!target||GetForegroundWindow()!=target)return Qnil;
    POINT p{};if(!GetCursorPos(&p)||!ScreenToClient(target,&p))return Qnil;
    RECT r{};GetClientRect(target,&r);int w,h,x,y;graphics_input_size(w,h);
    if(!rgss_display::locate(w,h,r.right,r.bottom,p.x,p.y,x,y))return Qnil;
    return rb_ary_new_from_args(2,INT2NUM(x),INT2NUM(y));
}
VALUE mouse_press_position(VALUE){
    if(!pressed_position||!target||GetForegroundWindow()!=target)return Qnil;
    RECT r{};GetClientRect(target,&r);int w,h,x,y;graphics_input_size(w,h);
    if(!rgss_display::locate(w,h,r.right,r.bottom,press_point.x,press_point.y,x,y))return Qnil;
    return rb_ary_new_from_args(2,INT2NUM(x),INT2NUM(y));
}
VALUE mouse_trigger(VALUE self,VALUE button){
    ID id=SYM2ID(rb_to_symbol(button));int key=id==rb_intern("left")?VK_LBUTTON:id==rb_intern("right")?VK_RBUTTON:0;
    if(!key)rb_raise(rb_eArgError,"Mouse button must be left or right");return key_trigger(self,INT2NUM(key));
}
VALUE wheel_delta(VALUE){return INT2NUM(wheel);}
VALUE text_value(const std::wstring& value){
    int size=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,value.data(),int(value.size()),nullptr,0,nullptr,nullptr);
    std::string bytes(size,'\0');if(size)WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,value.data(),int(value.size()),bytes.data(),size,nullptr,nullptr);
    return rb_utf8_str_new(bytes.data(),size);
}
VALUE text(VALUE){VALUE value=text_value(committed);committed.clear();return value;}
VALUE composing_text(VALUE){return text_value(composition);}
VALUE composing_now(VALUE){return composing?Qtrue:Qfalse;}
VALUE text_submit(VALUE){return submit.triggered?Qtrue:Qfalse;}
VALUE ime_open(VALUE){if(ime_owned&&!editing)return saved_open&&(saved_conversion&IME_CMODE_NATIVE)?Qtrue:Qfalse;HIMC context=target?ImmGetContext(target):nullptr;if(!context)return Qfalse;DWORD mode=0,sentence=0;ImmGetConversionStatus(context,&mode,&sentence);BOOL open=ImmGetOpenStatus(context);ImmReleaseContext(target,context);return open&&(mode&IME_CMODE_NATIVE)?Qtrue:Qfalse;}
VALUE set_ime_open(VALUE,VALUE value){
    if(!editing||!target)return Qfalse;
    HIMC context=ImmGetContext(target);if(!context)return Qfalse;
    DWORD mode=0,sentence=0;ImmGetConversionStatus(context,&mode,&sentence);
    BOOL result=ImmSetOpenStatus(context,TRUE);
    result=ImmSetConversionStatus(context,RTEST(value)?(mode|IME_CMODE_NATIVE):(mode&~IME_CMODE_NATIVE),sentence)&&result;
    ImmReleaseContext(target,context);place_ime();return result?Qtrue:Qfalse;
}
VALUE debug_stats(VALUE){
    HIMC context=target?ImmGetContext(target):nullptr;BOOL opened=context?ImmGetOpenStatus(context):FALSE;
    if(context)ImmReleaseContext(target,context);
    return rb_ary_new_from_args(8,ULONG2NUM(key_messages),ULONG2NUM(char_messages),ULONG2NUM(ime_messages),editing?Qtrue:Qfalse,
        target&&IsWindowUnicode(target)?Qtrue:Qfalse,ULONG2NUM(LOWORD(reinterpret_cast<ULONG_PTR>(GetKeyboardLayout(0)))),context?Qtrue:Qfalse,opened?Qtrue:Qfalse);
}
VALUE text_mode(VALUE,VALUE value){
    bool enabled=RTEST(value),first=!ime_owned;
    if(enabled&&target&&GetForegroundWindow()!=target)return value;
    if(first&&target){HIMC context=ImmGetContext(target);if(context){saved_open=ImmGetOpenStatus(context);ImmGetConversionStatus(context,&saved_conversion,&saved_sentence);ImmReleaseContext(target,context);}ime_owned=true;}
    if(editing==enabled&&!first)return value;
    if(!enabled)suspend_ime();
    else if(target){HIMC context=ImmGetContext(target);if(context){ImmSetConversionStatus(context,saved_conversion,saved_sentence);ImmSetOpenStatus(context,saved_open);ImmReleaseContext(target,context);}}
    editing=enabled;committed.clear();composition.clear();composing=false;ime_enter=false;last_ime_message=0;pending.fill(false);triggered.fill(false);submit.cancel();directions.clear_pending();place_ime();return value;
}
VALUE caret_rect(VALUE,VALUE value){
    int x=NUM2INT(rb_funcall(value,rb_intern("x"),0)),y=NUM2INT(rb_funcall(value,rb_intern("y"),0));
    int w=NUM2INT(rb_funcall(value,rb_intern("width"),0)),h=NUM2INT(rb_funcall(value,rb_intern("height"),0));
    if(x<0||y<0||w<1||h<1||x>4096||y>4096||w>4096||h>4096)rb_raise(rb_eArgError,"Invalid text caret rectangle");
    caret={x,y,x+w,y+h};place_ime();return value;
}
std::wstring ime_string(HIMC context,DWORD flag){
    LONG size=ImmGetCompositionStringW(context,flag,nullptr,0);if(size<=0||size>8192)return {};
    std::wstring value(size/sizeof(wchar_t),L'\0');ImmGetCompositionStringW(context,flag,value.data(),size);return value;
}
}
void ui_input_reset(){suspend_ime();held.fill(false);pending.fill(false);triggered.fill(false);directions.reset();submit.reset();pending_wheel=wheel=0;pending_position=pressed_position=false;committed.clear();composition.clear();composing=editing=ime_enter=false;}
void ui_input_update(){triggered=pending;pending.fill(false);directions.update();if(!(GetAsyncKeyState(VK_RETURN)&0x8000))submit.release();submit.update(editing,composing);wheel=pending_wheel;pending_wheel=0;press_point=pending_point;pressed_position=pending_position;pending_position=false;}
void ui_input_pretranslate(const MSG& message){
    if(message.hwnd!=target)return;
    const bool pressed=message.message==WM_KEYDOWN;
    if(!pressed&&message.message!=WM_KEYUP)return;
    // ImmGetVirtualKey loses the original key after TranslateMessage.
    UINT key=message.wParam==VK_PROCESSKEY&&pressed?ImmGetVirtualKey(target):UINT(message.wParam);
    if(key==VK_RETURN){if(pressed)submit.press(editing,composing,(message.lParam&(1<<30))!=0);else submit.release();}
    if(pressed&&key==VK_ESCAPE)submit.cancel();
}
bool ui_input_message(HWND window,UINT message,WPARAM wparam,LPARAM lparam){
    target=window;
    if(message==WM_KILLFOCUS){ui_input_reset();return false;}
    if(message==WM_KEYDOWN||message==WM_SYSKEYDOWN){
        ++key_messages;
        directions.press(arrow(wparam));
        if(wparam<256){if(!held[wparam])pending[wparam]=true;held[wparam]=true;}
        if(editing&&wparam==VK_RETURN&&(composing||ime_enter)){pending[VK_RETURN]=false;ime_enter=true;}
    }
    if(message==WM_KEYUP||message==WM_SYSKEYUP){directions.release(arrow(wparam));if(wparam<256)held[wparam]=false;if(wparam==VK_RETURN)ime_enter=false;}
    if(message==WM_LBUTTONDOWN||message==WM_RBUTTONDOWN){int k=message==WM_LBUTTONDOWN?VK_LBUTTON:VK_RBUTTON;pending[k]=!held[k];held[k]=true;
        if(k==VK_LBUTTON){pending_point={short(LOWORD(lparam)),short(HIWORD(lparam))};pending_position=true;}}
    if(message==WM_LBUTTONUP||message==WM_RBUTTONUP)held[message==WM_LBUTTONUP?VK_LBUTTON:VK_RBUTTON]=false;
    if(message==WM_MOUSEWHEEL)pending_wheel+=GET_WHEEL_DELTA_WPARAM(wparam)/WHEEL_DELTA;
    if(!editing)return false;
    if(message==WM_KEYDOWN&&wparam=='V'&&(GetKeyState(VK_CONTROL)&0x8000)){
        if(OpenClipboard(window)){
            HANDLE data=GetClipboardData(CF_UNICODETEXT);
            if(data){auto* content=static_cast<const wchar_t*>(GlobalLock(data));
                if(content){size_t limit=std::min<size_t>(GlobalSize(data)/sizeof(wchar_t),4096-committed.size());
                    for(size_t i=0;i<limit&&content[i];++i)if(content[i]>=32)committed+=content[i];GlobalUnlock(data);}}
            CloseClipboard();
        }
        return true;
    }
    if(message==WM_IME_SETCONTEXT){DefWindowProcW(window,message,wparam,lparam&~ISC_SHOWUICOMPOSITIONWINDOW);return true;}
    if(message==WM_IME_STARTCOMPOSITION){last_ime_message=GetTickCount64();composing=true;place_ime();return true;}
    if(message==WM_IME_ENDCOMPOSITION){last_ime_message=GetTickCount64();composing=false;composition.clear();return true;}
    if(message==WM_IME_COMPOSITION){
        ++ime_messages;
        last_ime_message=GetTickCount64();
        HIMC context=ImmGetContext(window);
        if(context){
            if(lparam&GCS_RESULTSTR){auto result=ime_string(context,GCS_RESULTSTR);if(committed.size()+result.size()<=4096)committed+=result;composition.clear();submit.committed();}
            if(lparam&GCS_COMPSTR)composition=ime_string(context,GCS_COMPSTR);
            if(!lparam){composition.clear();composing=false;}
            ImmReleaseContext(window,context);
        }
        // Consumed result strings must not also become WM_CHAR through DefWindowProc.
        return true;
    }
    if(message==WM_CHAR){++char_messages;if(wparam>=32&&wparam!=127&&committed.size()<4096)committed+=wchar_t(wparam);return true;}
    return false;
}
void init_ui_input(){
    VALUE root=rb_define_module("Lunetile"),input=rb_define_module_under(root,"UIInput");
    rb_define_singleton_method(input,"key_trigger?",RUBY_METHOD_FUNC(key_trigger),1);
    rb_define_singleton_method(input,"key_press?",RUBY_METHOD_FUNC(key_press),1);
    rb_define_singleton_method(input,"direction4",RUBY_METHOD_FUNC(direction4),0);
    rb_define_singleton_method(input,"direction_trigger",RUBY_METHOD_FUNC(direction_trigger),0);
    rb_define_singleton_method(input,"mouse_position",RUBY_METHOD_FUNC(mouse_position),0);
    rb_define_singleton_method(input,"mouse_press_position",RUBY_METHOD_FUNC(mouse_press_position),0);
    rb_define_singleton_method(input,"mouse_trigger?",RUBY_METHOD_FUNC(mouse_trigger),1);
    rb_define_singleton_method(input,"wheel_delta",RUBY_METHOD_FUNC(wheel_delta),0);
    rb_define_singleton_method(input,"text",RUBY_METHOD_FUNC(text),0);
    rb_define_singleton_method(input,"composition",RUBY_METHOD_FUNC(composing_text),0);
    rb_define_singleton_method(input,"composing?",RUBY_METHOD_FUNC(composing_now),0);
    rb_define_singleton_method(input,"text_submit?",RUBY_METHOD_FUNC(text_submit),0);
    rb_define_singleton_method(input,"ime_open?",RUBY_METHOD_FUNC(ime_open),0);
    rb_define_singleton_method(input,"ime_open=",RUBY_METHOD_FUNC(set_ime_open),1);
    rb_define_singleton_method(input,"text_input=",RUBY_METHOD_FUNC(text_mode),1);
    rb_define_singleton_method(input,"caret_rect=",RUBY_METHOD_FUNC(caret_rect),1);
    rb_define_singleton_method(input,"__stats",RUBY_METHOD_FUNC(debug_stats),0);
}
