#include <windows.h>
#include <shlobj.h>
#include <bcrypt.h>
#include <winhttp.h>
#include <wrl.h>
#include <WebView2.h>
#include <algorithm>
#include <atomic>
#include <cmath>
#include <filesystem>
#include <memory>
#include <new>
#include <string>
#include <vector>
#include <ruby.h>
#include <ruby/encoding.h>
#include "browser.h"
#include "graphics.h"
#include "display_geometry.h"
#include "ui_input.h"

namespace {
using Microsoft::WRL::ComPtr;
using Microsoft::WRL::Callback;
namespace fs = std::filesystem;
constexpr wchar_t host_name[] = L"lunetile-web.invalid";
constexpr UINT close_message = WM_APP + 0x52;
constexpr UINT collect_message = WM_APP + 0x53;
enum Status { Creating, Ready, Loading, Failed, Disposed };
const char* status_names[] = {"creating","ready","loading","failed","disposed"};
HWND game_window = nullptr;
DWORD owner_thread = 0;
bool apartment_owned = false, finalizing = false;
unsigned long long next_generation = 0;
std::atomic<unsigned long> pending_creations{0};
struct Failure { const char* code; HRESULT native; };
void checked(HRESULT result, const char* code) { if(FAILED(result))throw Failure{code,result}; }

std::wstring wide(const char* bytes, long size) {
    int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,bytes,size,nullptr,0);
    if(!n)throw Failure{"argument",E_INVALIDARG};
    std::wstring value(n,L'\0');MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,bytes,size,value.data(),n);return value;
}
bool web_url(const std::wstring& value) {
    if(value.size()>8192||value.find_first_of(L"\r\n\t \\")!=std::wstring::npos)return false;
    URL_COMPONENTS parts{};parts.dwStructSize=sizeof(parts);parts.dwHostNameLength=DWORD(-1);parts.dwSchemeLength=DWORD(-1);
    return WinHttpCrackUrl(value.c_str(),DWORD(value.size()),0,&parts)&&parts.dwHostNameLength&&
        (parts.nScheme==INTERNET_SCHEME_HTTP||parts.nScheme==INTERNET_SCHEME_HTTPS);
}
fs::path project_directory() {
    std::wstring name(32768,L'\0');DWORD size=GetModuleFileNameW(nullptr,name.data(),DWORD(name.size()));
    if(!size||size>=name.size())throw Failure{"project_path",HRESULT_FROM_WIN32(GetLastError())};
    name.resize(size);return fs::canonical(fs::path(name).parent_path());
}
std::wstring profile_directory() {
    auto key=project_directory().wstring();
#ifdef RGSS_VXA
    key=L"vxa|"+key;
#else
    key=L"xp|"+key;
#endif
    std::wstring normalized(key.size(),L'\0');
    if(!LCMapStringEx(LOCALE_NAME_INVARIANT,LCMAP_LOWERCASE,key.data(),int(key.size()),normalized.data(),int(normalized.size()),nullptr,nullptr,0))throw Failure{"project_path",E_FAIL};
    BCRYPT_ALG_HANDLE algorithm=nullptr;unsigned char hash[32]{};
    BCRYPT_HASH_HANDLE hashing=nullptr;
    NTSTATUS result=BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0);
    if(result>=0)result=BCryptCreateHash(algorithm,&hashing,nullptr,0,nullptr,0,0);
    if(result>=0)result=BCryptHashData(hashing,reinterpret_cast<PUCHAR>(normalized.data()),ULONG(normalized.size()*sizeof(wchar_t)),0);
    if(result>=0)result=BCryptFinishHash(hashing,hash,sizeof(hash),0);
    if(hashing)BCryptDestroyHash(hashing);if(algorithm)BCryptCloseAlgorithmProvider(algorithm,0);
    if(result<0)throw Failure{"profile_hash",HRESULT_FROM_NT(result)};
    std::wstring suffix;constexpr wchar_t digits[]=L"0123456789abcdef";
    for(auto b:hash){suffix+=digits[b>>4];suffix+=digits[b&15];}
    PWSTR local=nullptr;checked(SHGetKnownFolderPath(FOLDERID_LocalAppData,0,nullptr,&local),"profile_path");
    fs::path directory=fs::path(local)/L"Lunetile"/L"WebView2"/suffix;CoTaskMemFree(local);
    fs::create_directories(directory);return directory.wstring();
}
bool inside(const fs::path& path,const fs::path& root) {
    auto p=path.begin();for(auto r=root.begin();r!=root.end();++r,++p)if(p==path.end()||_wcsicmp(p->c_str(),r->c_str()))return false;return true;
}
std::wstring local_url(const std::wstring& relative,std::wstring& folder) {
    fs::path name(relative);
    if(name.is_absolute()||name.has_root_name()||name.has_root_directory())throw Failure{"local_path",E_INVALIDARG};
    for(auto& part:name)if(part==L".."||part.wstring().find(L':')!=std::wstring::npos)throw Failure{"local_path",E_ACCESSDENIED};
    auto project=project_directory(),root=fs::canonical(project/L"Web"),path=fs::canonical(project/name);
    if(!inside(root,project)||!inside(path,root)||!fs::is_regular_file(path))throw Failure{"local_path",E_ACCESSDENIED};
    auto extension=path.extension().wstring();
    if(_wcsicmp(extension.c_str(),L".html")&&_wcsicmp(extension.c_str(),L".htm"))throw Failure{"local_path",E_INVALIDARG};
    // Folder mapping must never expose a junction/symlink to files outside Web/.
    if(GetFileAttributesW((project/L"Web").c_str())&FILE_ATTRIBUTE_REPARSE_POINT)throw Failure{"local_path",E_ACCESSDENIED};
    for(auto& entry:fs::recursive_directory_iterator(root))
        if(GetFileAttributesW(entry.path().c_str())&FILE_ATTRIBUTE_REPARSE_POINT)throw Failure{"local_path",E_ACCESSDENIED};
    auto tail=path.lexically_relative(root).generic_u8string();std::wstring encoded;
    constexpr wchar_t digits[]=L"0123456789ABCDEF";
    for(unsigned char c:tail){if((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='/'||c=='-'||c=='_'||c=='.'||c=='~')encoded+=wchar_t(c);else{encoded+=L'%';encoded+=digits[c>>4];encoded+=digits[c&15];}}
    folder=root.wstring();return std::wstring(L"https://")+host_name+L"/"+encoded;
}

struct Panel;
std::shared_ptr<Panel> active;
void close_panel(const std::shared_ptr<Panel>& panel);
LRESULT CALLBACK panel_proc(HWND,UINT,WPARAM,LPARAM);
struct Panel {
    Status status=Creating;
    std::atomic<bool> collected{false};
    unsigned long long generation=++next_generation, navigation=0;
    int x=0,y=0,width=0,height=0;
    bool visible=true,focused=false,want_focus=false,configured=false;
    HWND window=nullptr,header=nullptr,button=nullptr;
    HFONT font=nullptr;int font_size=0;
    std::wstring pending_url,folder;
    const char* error_code=nullptr;HRESULT native_error=S_OK;
    ComPtr<ICoreWebView2Environment> environment;
    ComPtr<ICoreWebView2Controller> controller;
    ComPtr<ICoreWebView2> view;
    ComPtr<ICoreWebView2_3> local;
    ComPtr<ICoreWebView2_4> downloads;
    ComPtr<ICoreWebView2_18> external;
    EventRegistrationToken starting{},completed{},popup{},permission{},download{},launch{},process{},accelerator{},got_focus{},lost_focus{},move_focus{};
    void fail(const char* code,HRESULT native) {if(status!=Disposed){error_code=code;native_error=native;status=Failed;}}
    void navigate() {
        if(!configured||pending_url.empty()||status==Disposed)return;
        HRESULT result=S_OK;
        if(!folder.empty())result=local->SetVirtualHostNameToFolderMapping(host_name,folder.c_str(),COREWEBVIEW2_HOST_RESOURCE_ACCESS_KIND_DENY);
        if(SUCCEEDED(result)){status=Loading;error_code=nullptr;native_error=S_OK;result=view->Navigate(pending_url.c_str());}
        if(FAILED(result))fail("navigation",result);
    }
    void layout() {
        if(!window||status==Disposed||!game_window)return;
        RECT client{};GetClientRect(game_window,&client);int sw,sh;graphics_input_size(sw,sh);
        if(client.right<=0||client.bottom<=0||sw<=0||sh<=0){ShowWindow(window,SW_HIDE);ShowWindow(header,SW_HIDE);return;}
        auto fit=rgss_display::fit(float(sw),float(sh),float(client.right),float(client.bottom));
        double scale=fit.width/sw;
        int left=int(std::floor(fit.x+x*scale)),top=int(std::floor(fit.y+y*scale));
        int w=std::max(1,int(std::ceil(fit.x+(x+width)*scale))-left),h=std::max(1,int(std::ceil(fit.y+(y+height)*scale))-top);
        RECT clip{std::max(0,int(std::ceil(fit.x))-left),std::max(0,int(std::ceil(fit.y))-top),std::min(w,int(std::floor(fit.x+fit.width))-left),std::min(h,int(std::floor(fit.y+fit.height))-top)};
        SetWindowPos(window,HWND_TOP,left,top,w,h,SWP_NOACTIVATE);
        HRGN region=CreateRectRgn(clip.left,clip.top,std::max(clip.left,clip.right),std::max(clip.top,clip.bottom));
        if(region&&!SetWindowRgn(window,region,TRUE))DeleteObject(region);
        int bar=std::min(h-1,std::max(1,int(std::ceil(24*scale))));
        POINT origin{left,top};ClientToScreen(game_window,&origin);
        SetWindowPos(header,HWND_TOP,origin.x,origin.y,w,bar,SWP_NOACTIVATE);
        HRGN chrome=CreateRectRgn(clip.left,clip.top,std::max(clip.left,clip.right),std::max(clip.top,std::min<LONG>(bar,clip.bottom)));
        if(chrome&&!SetWindowRgn(header,chrome,TRUE))DeleteObject(chrome);
        SetWindowPos(button,HWND_TOP,std::max(0,w-bar),0,bar,bar,SWP_NOACTIVATE);
        int size=std::max(10,int(bar*.7));
        if(size!=font_size){
            HFONT next=CreateFontW(-size,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,OUT_DEFAULT_PRECIS,CLIP_DEFAULT_PRECIS,DEFAULT_QUALITY,DEFAULT_PITCH,L"Segoe UI");
            if(next){SendMessageW(button,WM_SETFONT,reinterpret_cast<WPARAM>(next),TRUE);if(font)DeleteObject(font);font=next;font_size=size;}
        }
        bool show=visible&&clip.right>clip.left&&clip.bottom>clip.top&&IsWindowVisible(game_window)&&!IsIconic(game_window);
        ShowWindow(window,show?SW_SHOWNOACTIVATE:SW_HIDE);
        ShowWindow(header,show&&clip.top<bar?SW_SHOWNOACTIVATE:SW_HIDE);
        if(controller){
            RECT bounds{0,bar,w,h};HRESULT result=controller->put_Bounds(bounds);
            if(SUCCEEDED(result))result=controller->put_IsVisible(show);
            if(SUCCEEDED(result))result=controller->NotifyParentWindowPositionChanged();
            if(FAILED(result))fail("layout",result);
            if(show&&want_focus){want_focus=false;result=controller->MoveFocus(COREWEBVIEW2_MOVE_FOCUS_REASON_PROGRAMMATIC);if(FAILED(result))fail("focus",result);}
        }
    }
};

void close_panel(const std::shared_ptr<Panel>& panel) {
    if(!panel||panel->status==Disposed)return;
    bool restore=panel->focused||(panel->window&&(GetFocus()==panel->window||IsChild(panel->window,GetFocus())))||(panel->header&&(GetFocus()==panel->header||IsChild(panel->header,GetFocus())));
    panel->status=Disposed;panel->collected=true;panel->focused=false;panel->want_focus=false;
    if(panel->view){
        panel->view->remove_NavigationStarting(panel->starting);panel->view->remove_NavigationCompleted(panel->completed);
        panel->view->remove_NewWindowRequested(panel->popup);panel->view->remove_PermissionRequested(panel->permission);panel->view->remove_ProcessFailed(panel->process);
    }
    if(panel->downloads)panel->downloads->remove_DownloadStarting(panel->download);
    if(panel->external)panel->external->remove_LaunchingExternalUriScheme(panel->launch);
    if(panel->controller){
        panel->controller->remove_AcceleratorKeyPressed(panel->accelerator);panel->controller->remove_GotFocus(panel->got_focus);panel->controller->remove_LostFocus(panel->lost_focus);panel->controller->remove_MoveFocusRequested(panel->move_focus);
        panel->controller->Close();
    }
    panel->external.Reset();panel->downloads.Reset();panel->local.Reset();panel->view.Reset();panel->controller.Reset();panel->environment.Reset();
    if(panel->header){DestroyWindow(panel->header);panel->header=nullptr;}
    if(panel->window){HWND window=panel->window;panel->window=nullptr;DestroyWindow(window);}
    if(panel->font){DeleteObject(panel->font);panel->font=nullptr;}
    panel->button=nullptr;panel->pending_url.clear();panel->folder.clear();
    if(active==panel)active.reset();
    if(restore&&game_window&&GetForegroundWindow()==game_window)SetFocus(game_window);
    if(restore)input_browser_release();
}
LRESULT CALLBACK panel_proc(HWND window,UINT message,WPARAM wparam,LPARAM lparam) {
    auto* panel=reinterpret_cast<Panel*>(GetWindowLongPtrW(window,GWLP_USERDATA));
    if(message==WM_NCCREATE){panel=static_cast<Panel*>(reinterpret_cast<CREATESTRUCTW*>(lparam)->lpCreateParams);SetWindowLongPtrW(window,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(panel));}
    if(panel){
        if(message==WM_MOUSEACTIVATE)return MA_NOACTIVATE;
        if((message==close_message&&wparam==static_cast<WPARAM>(panel->generation))||(message==WM_COMMAND&&LOWORD(wparam)==1&&HIWORD(wparam)==BN_CLICKED)){
            auto keep=active;if(keep.get()==panel)close_panel(keep);return 0;
        }
        if(message==WM_PAINT){PAINTSTRUCT paint{};HDC dc=BeginPaint(window,&paint);FillRect(dc,&paint.rcPaint,GetSysColorBrush(COLOR_BTNFACE));EndPaint(window,&paint);return 0;}
        if(message==WM_ERASEBKGND)return 1;
    }
    return DefWindowProcW(window,message,wparam,lparam);
}
bool shortcut(const std::shared_ptr<Panel>& panel,UINT message,WPARAM key,LPARAM flags) {
    bool down=message==WM_KEYDOWN||message==WM_SYSKEYDOWN,up=message==WM_KEYUP||message==WM_SYSKEYUP;
    if(!down&&!up)return false;
    if(key==VK_ESCAPE){if(down&&!(flags&(1L<<30)))PostMessageW(panel->window,close_message,static_cast<WPARAM>(panel->generation),0);return true;}
    if(key==VK_F12||(key==VK_RETURN&&(flags&(1L<<29)))){PostMessageW(game_window,message,key,flags);return true;}
    return false;
}
void configure(const std::shared_ptr<Panel>& panel) {
    auto weak=std::weak_ptr<Panel>(panel);
    checked(panel->controller->get_CoreWebView2(&panel->view),"controller");
    checked(panel->view.As(&panel->local),"runtime_version");checked(panel->view.As(&panel->downloads),"runtime_version");
    checked(panel->view.As(&panel->external),"runtime_version");
    ComPtr<ICoreWebView2Settings> settings;checked(panel->view->get_Settings(&settings),"settings");
    checked(settings->put_IsWebMessageEnabled(FALSE),"settings");checked(settings->put_AreHostObjectsAllowed(FALSE),"settings");
    checked(settings->put_AreDevToolsEnabled(FALSE),"settings");checked(settings->put_IsStatusBarEnabled(FALSE),"settings");
    checked(settings->put_AreDefaultScriptDialogsEnabled(FALSE),"settings");
    ComPtr<ICoreWebView2Settings3> settings3;checked(settings.As(&settings3),"runtime_version");checked(settings3->put_AreBrowserAcceleratorKeysEnabled(FALSE),"settings");
    checked(panel->view->add_NavigationStarting(Callback<ICoreWebView2NavigationStartingEventHandler>([weak](ICoreWebView2*,ICoreWebView2NavigationStartingEventArgs* args)->HRESULT {
        auto p=weak.lock();if(!p||p->status==Disposed){args->put_Cancel(TRUE);return S_OK;}
        LPWSTR value=nullptr;HRESULT hr=args->get_Uri(&value);
        if(FAILED(hr)){p->fail("navigation",hr);args->put_Cancel(TRUE);return S_OK;}
        bool valid=false;try{valid=web_url(value);}catch(...){p->fail("allocation",E_OUTOFMEMORY);}CoTaskMemFree(value);
        if(!valid){args->put_Cancel(TRUE);p->fail("navigation_blocked",E_ACCESSDENIED);return S_OK;}
        args->get_NavigationId(&p->navigation);p->status=Loading;p->error_code=nullptr;return S_OK;
    }).Get(),&panel->starting),"events");
    checked(panel->view->add_NavigationCompleted(Callback<ICoreWebView2NavigationCompletedEventHandler>([weak](ICoreWebView2*,ICoreWebView2NavigationCompletedEventArgs* args)->HRESULT {
        auto p=weak.lock();if(!p||p->status==Disposed)return S_OK;
        UINT64 id=0;args->get_NavigationId(&id);if(id!=p->navigation)return S_OK;
        BOOL success=FALSE;HRESULT hr=args->get_IsSuccess(&success);if(FAILED(hr)){p->fail("navigation",hr);return S_OK;}
        if(success){p->status=Ready;p->error_code=nullptr;p->native_error=S_OK;}
        else{COREWEBVIEW2_WEB_ERROR_STATUS error{};args->get_WebErrorStatus(&error);p->fail("navigation",HRESULT(error));}
        return S_OK;
    }).Get(),&panel->completed),"events");
    checked(panel->view->add_NewWindowRequested(Callback<ICoreWebView2NewWindowRequestedEventHandler>([weak](ICoreWebView2*,ICoreWebView2NewWindowRequestedEventArgs* args)->HRESULT {
        args->put_Handled(TRUE);auto p=weak.lock();if(!p||p->status==Disposed)return S_OK;
        LPWSTR uri=nullptr;HRESULT hr=args->get_Uri(&uri);if(FAILED(hr)){p->fail("navigation",hr);return S_OK;}
        try{if(web_url(uri)){p->pending_url=uri;PostMessageW(p->window,collect_message,0,0);}else{p->fail("navigation_blocked",E_ACCESSDENIED);}}
        catch(...){p->fail("allocation",E_OUTOFMEMORY);}CoTaskMemFree(uri);return S_OK;
    }).Get(),&panel->popup),"events");
    checked(panel->view->add_PermissionRequested(Callback<ICoreWebView2PermissionRequestedEventHandler>([](ICoreWebView2*,ICoreWebView2PermissionRequestedEventArgs* args)->HRESULT {args->put_State(COREWEBVIEW2_PERMISSION_STATE_DENY);return S_OK;}).Get(),&panel->permission),"events");
    checked(panel->downloads->add_DownloadStarting(Callback<ICoreWebView2DownloadStartingEventHandler>([](ICoreWebView2*,ICoreWebView2DownloadStartingEventArgs* args)->HRESULT {args->put_Cancel(TRUE);args->put_Handled(TRUE);return S_OK;}).Get(),&panel->download),"events");
    checked(panel->external->add_LaunchingExternalUriScheme(Callback<ICoreWebView2LaunchingExternalUriSchemeEventHandler>([weak](ICoreWebView2*,ICoreWebView2LaunchingExternalUriSchemeEventArgs* args)->HRESULT {args->put_Cancel(TRUE);auto p=weak.lock();if(p)p->fail("navigation_blocked",E_ACCESSDENIED);return S_OK;}).Get(),&panel->launch),"events");
    checked(panel->view->add_ProcessFailed(Callback<ICoreWebView2ProcessFailedEventHandler>([weak](ICoreWebView2*,ICoreWebView2ProcessFailedEventArgs* args)->HRESULT {auto p=weak.lock();COREWEBVIEW2_PROCESS_FAILED_KIND kind{};args->get_ProcessFailedKind(&kind);if(p)p->fail("process",HRESULT(kind));return S_OK;}).Get(),&panel->process),"events");
    checked(panel->controller->add_AcceleratorKeyPressed(Callback<ICoreWebView2AcceleratorKeyPressedEventHandler>([weak](ICoreWebView2Controller*,ICoreWebView2AcceleratorKeyPressedEventArgs* args)->HRESULT {
        auto p=weak.lock();if(!p||p->status==Disposed)return S_OK;
        COREWEBVIEW2_KEY_EVENT_KIND kind{};UINT key=0;INT flags=0;args->get_KeyEventKind(&kind);args->get_VirtualKey(&key);args->get_KeyEventLParam(&flags);
        UINT message=kind==COREWEBVIEW2_KEY_EVENT_KIND_KEY_DOWN?WM_KEYDOWN:kind==COREWEBVIEW2_KEY_EVENT_KIND_KEY_UP?WM_KEYUP:kind==COREWEBVIEW2_KEY_EVENT_KIND_SYSTEM_KEY_DOWN?WM_SYSKEYDOWN:WM_SYSKEYUP;
        if(shortcut(p,message,key,flags))args->put_Handled(TRUE);return S_OK;
    }).Get(),&panel->accelerator),"events");
    checked(panel->controller->add_GotFocus(Callback<ICoreWebView2FocusChangedEventHandler>([weak](ICoreWebView2Controller*,IUnknown*)->HRESULT {auto p=weak.lock();if(p&&p->status!=Disposed){p->focused=true;input_browser_release();}return S_OK;}).Get(),&panel->got_focus),"events");
    checked(panel->controller->add_LostFocus(Callback<ICoreWebView2FocusChangedEventHandler>([weak](ICoreWebView2Controller*,IUnknown*)->HRESULT {auto p=weak.lock();if(p&&p->focused){p->focused=false;input_browser_release();}return S_OK;}).Get(),&panel->lost_focus),"events");
    checked(panel->controller->add_MoveFocusRequested(Callback<ICoreWebView2MoveFocusRequestedEventHandler>([weak](ICoreWebView2Controller*,ICoreWebView2MoveFocusRequestedEventArgs* args)->HRESULT {auto p=weak.lock();if(p&&p->status!=Disposed){args->put_Handled(TRUE);SetFocus(game_window);}return S_OK;}).Get(),&panel->move_focus),"events");
    panel->configured=true;panel->status=Ready;panel->layout();panel->navigate();
}
bool runtime_available() {LPWSTR version=nullptr;HRESULT result=GetAvailableCoreWebView2BrowserVersionString(nullptr,&version);CoTaskMemFree(version);return SUCCEEDED(result);}
void start(const std::shared_ptr<Panel>& panel) {
    if(!runtime_available())throw Failure{"runtime_missing",HRESULT_FROM_WIN32(ERROR_FILE_NOT_FOUND)};
    if(!apartment_owned){checked(CoInitializeEx(nullptr,COINIT_APARTMENTTHREADED),"apartment");apartment_owned=true;}
    // SDK completions may outlive RGSSFinalize; keep their code mapped until process exit.
    HMODULE pinned=nullptr;checked(GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS|GET_MODULE_HANDLE_EX_FLAG_PIN,reinterpret_cast<LPCWSTR>(&start),&pinned)?S_OK:HRESULT_FROM_WIN32(GetLastError()),"module_lifetime");
    WNDCLASSW klass{};klass.lpfnWndProc=panel_proc;klass.hInstance=GetModuleHandleW(nullptr);klass.lpszClassName=L"LunetileBrowserPanel";klass.hCursor=LoadCursorW(nullptr,MAKEINTRESOURCEW(32512));
    if(!RegisterClassW(&klass)&&GetLastError()!=ERROR_CLASS_ALREADY_EXISTS)throw Failure{"window",HRESULT_FROM_WIN32(GetLastError())};
    klass.lpszClassName=L"LunetileBrowserChrome";
    if(!RegisterClassW(&klass)&&GetLastError()!=ERROR_CLASS_ALREADY_EXISTS)throw Failure{"window",HRESULT_FROM_WIN32(GetLastError())};
    klass.lpszClassName=L"LunetileBrowserPanel";
    panel->window=CreateWindowExW(0,klass.lpszClassName,L"Browser",WS_CHILD|WS_CLIPCHILDREN|WS_CLIPSIBLINGS,0,0,1,1,game_window,nullptr,klass.hInstance,panel.get());
    if(!panel->window)throw Failure{"window",HRESULT_FROM_WIN32(GetLastError())};
    // Flip-model presentation overwrites GDI children; keep chrome in a nonactivating owned surface.
    panel->header=CreateWindowExW(WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE,L"LunetileBrowserChrome",L"",WS_POPUP|WS_CLIPCHILDREN,0,0,1,1,game_window,nullptr,klass.hInstance,panel.get());
    if(!panel->header)throw Failure{"window",HRESULT_FROM_WIN32(GetLastError())};
    panel->button=CreateWindowExW(0,L"BUTTON",L"\x00d7",WS_CHILD|WS_VISIBLE|BS_PUSHBUTTON,0,0,1,1,panel->header,reinterpret_cast<HMENU>(1),klass.hInstance,nullptr);
    if(!panel->button)throw Failure{"window",HRESULT_FROM_WIN32(GetLastError())};
    panel->layout();auto folder=profile_directory();auto weak=std::weak_ptr<Panel>(panel);
    ++pending_creations;
    HRESULT result=CreateCoreWebView2EnvironmentWithOptions(nullptr,folder.c_str(),nullptr,Callback<ICoreWebView2CreateCoreWebView2EnvironmentCompletedHandler>([weak](HRESULT result,ICoreWebView2Environment* environment)->HRESULT {
        --pending_creations;auto p=weak.lock();if(!p||p->status==Disposed||p->collected)return S_OK;
        if(FAILED(result)||!environment){p->fail("environment",FAILED(result)?result:E_POINTER);return S_OK;}
        p->environment=environment;++pending_creations;
        HRESULT creating=environment->CreateCoreWebView2Controller(p->window,Callback<ICoreWebView2CreateCoreWebView2ControllerCompletedHandler>([weak](HRESULT result,ICoreWebView2Controller* controller)->HRESULT {
            --pending_creations;auto p=weak.lock();if(!p||p->status==Disposed||p->collected){if(controller)controller->Close();return S_OK;}
            if(FAILED(result)||!controller){p->fail("controller",FAILED(result)?result:E_POINTER);return S_OK;}
            p->controller=controller;
            try{configure(p);}catch(const Failure& failure){p->fail(failure.code,failure.native);}catch(...){p->fail("allocation",E_OUTOFMEMORY);}
            return S_OK;
        }).Get());
        if(FAILED(creating)){--pending_creations;p->fail("controller",creating);}return S_OK;
    }).Get());
    if(FAILED(result)){--pending_creations;throw Failure{"environment",result};}
}

struct Box {std::shared_ptr<Panel> panel;};
void free_box(void* raw) {
    auto* box=static_cast<Box*>(raw);
    if(box->panel){box->panel->collected=true;PostThreadMessageW(owner_thread,WM_NULL,0,0);}
    box->~Box();ruby_xfree(box);
}
size_t box_size(const void* raw){auto* box=static_cast<const Box*>(raw);return sizeof(Box)+(box->panel?sizeof(Panel):0);}
const rb_data_type_t box_type={"Lunetile::Browser",{nullptr,free_box,box_size,nullptr},nullptr,nullptr,RUBY_TYPED_FREE_IMMEDIATELY};
VALUE allocate(VALUE klass){Box* box;VALUE object=TypedData_Make_Struct(klass,Box,&box_type,box);new(box)Box{};return object;}
void thread_check(){if(GetCurrentThreadId()!=owner_thread)rb_raise(rb_eThreadError,"Browser requires the game thread");}
void raise_failure(const char* code,HRESULT native){VALUE error=rb_path2class("Lunetile::BrowserError");VALUE args[]={ID2SYM(rb_intern(code)),ULONG2NUM(static_cast<unsigned long>(native))};rb_exc_raise(rb_class_new_instance(2,args,error));}
Box* get(VALUE self,bool live=true){thread_check();Box* box;TypedData_Get_Struct(self,Box,&box_type,box);if(!box->panel)raise_failure("uninitialized",E_UNEXPECTED);if(live&&box->panel->status==Disposed)raise_failure("disposed",RO_E_CLOSED);if(live&&box->panel->status==Failed&&!box->panel->configured)raise_failure(box->panel->error_code,box->panel->native_error);return box;}
VALUE available(VALUE){thread_check();return runtime_available()?Qtrue:Qfalse;}
VALUE create(VALUE self,VALUE x,VALUE y,VALUE width,VALUE height) {
    thread_check();Box* box;TypedData_Get_Struct(self,Box,&box_type,box);
    if(finalizing||!game_window||!IsWindow(game_window))raise_failure("not_attached",E_UNEXPECTED);
    if(box->panel)raise_failure("already_initialized",E_UNEXPECTED);
    browser_pump();if(active)raise_failure("already_open",E_UNEXPECTED);
    int px=NUM2INT(x),py=NUM2INT(y),pw=NUM2INT(width),ph=NUM2INT(height);
    if(px<-4096||px>4096||py<-4096||py>4096||pw<32||pw>4096||ph<32||ph>4096)rb_raise(rb_eArgError,"Invalid Browser rectangle");
    const char* error=nullptr;HRESULT native=S_OK;
    try{
        auto panel=std::make_shared<Panel>();panel->x=px;panel->y=py;panel->width=pw;panel->height=ph;
        box->panel=panel;active=panel;start(panel);
    }catch(const Failure& f){error=f.code;native=f.native;}catch(const fs::filesystem_error&){error="profile_path";native=E_ACCESSDENIED;}catch(...){error="allocation";native=E_OUTOFMEMORY;}
    if(error){close_panel(box->panel);raise_failure(error,native);}return self;
}
VALUE navigate(VALUE self,VALUE value) {
    auto* box=get(self);StringValue(value);const char* error=nullptr;HRESULT native=S_OK;
    try{auto url=wide(RSTRING_PTR(value),RSTRING_LEN(value));if(!web_url(url))throw Failure{"url",E_INVALIDARG};box->panel->pending_url=std::move(url);box->panel->navigate();}
    catch(const Failure& f){error=f.code;native=f.native;}catch(...){error="allocation";native=E_OUTOFMEMORY;}
    if(error)raise_failure(error,native);return self;
}
VALUE load_file(VALUE self,VALUE value) {
    auto* box=get(self);StringValue(value);const char* error=nullptr;HRESULT native=S_OK;
    try{auto path=wide(RSTRING_PTR(value),RSTRING_LEN(value));box->panel->pending_url=local_url(path,box->panel->folder);box->panel->navigate();}
    catch(const Failure& f){error=f.code;native=f.native;}catch(const fs::filesystem_error&){error="local_path";native=E_ACCESSDENIED;}catch(...){error="allocation";native=E_OUTOFMEMORY;}
    if(error)raise_failure(error,native);return self;
}
VALUE reload(VALUE self){auto* p=get(self)->panel.get();if(!p->configured)raise_failure("not_ready",E_PENDING);HRESULT result=p->view->Reload();if(FAILED(result))p->fail("navigation",result);return self;}
VALUE get_rect(VALUE self){auto* p=get(self)->panel.get();return rb_ary_new_from_args(4,INT2NUM(p->x),INT2NUM(p->y),INT2NUM(p->width),INT2NUM(p->height));}
VALUE set_rect(VALUE self,VALUE x,VALUE y,VALUE width,VALUE height){auto* p=get(self)->panel.get();int px=NUM2INT(x),py=NUM2INT(y),pw=NUM2INT(width),ph=NUM2INT(height);if(px<-4096||px>4096||py<-4096||py>4096||pw<32||pw>4096||ph<32||ph>4096)rb_raise(rb_eArgError,"Invalid Browser rectangle");p->x=px;p->y=py;p->width=pw;p->height=ph;p->layout();return self;}
VALUE visible(VALUE self){return get(self)->panel->visible?Qtrue:Qfalse;}
VALUE set_visible(VALUE self,VALUE value){auto* p=get(self)->panel.get();if(value!=Qtrue&&value!=Qfalse)rb_raise(rb_eTypeError,"visible must be true or false");bool was_focused=browser_input_blocked();p->visible=RTEST(value);if(!p->visible&&was_focused){SetFocus(game_window);input_browser_release();}p->layout();return value;}
VALUE focus(VALUE self){auto* p=get(self)->panel.get();p->want_focus=true;p->layout();return self;}
VALUE blur(VALUE self){auto* p=get(self)->panel.get();p->want_focus=false;if(browser_input_blocked()){SetFocus(game_window);input_browser_release();}return self;}
VALUE dispose(VALUE self){auto* box=get(self,false);close_panel(box->panel);return Qnil;}
VALUE disposed(VALUE self){return get(self,false)->panel->status==Disposed?Qtrue:Qfalse;}
VALUE state(VALUE self){return ID2SYM(rb_intern(status_names[get(self,false)->panel->status]));}
VALUE error(VALUE self){auto* p=get(self,false)->panel.get();return p->error_code?rb_ary_new_from_args(2,ID2SYM(rb_intern(p->error_code)),ULONG2NUM(static_cast<unsigned long>(p->native_error))):Qnil;}
}

void browser_attach(HWND window){game_window=window;owner_thread=GetCurrentThreadId();finalizing=false;}
void browser_reset(){if(active)close_panel(active);}
void browser_shutdown(){finalizing=true;browser_reset();if(apartment_owned){CoUninitialize();apartment_owned=false;}game_window=nullptr;}
void browser_layout(){if(active)active->layout();}
void browser_pump(){if(active&&active->collected)close_panel(active);}
bool browser_input_blocked(){auto* p=active.get();if(!p||!p->visible||p->status==Disposed||!p->window)return false;HWND focus=GetFocus();return p->focused||focus==p->window||IsChild(p->window,focus)||focus==p->header||IsChild(p->header,focus);}
bool browser_pretranslate(const MSG& message){
    auto p=active;if(!p||p->status==Disposed)return false;
    if(message.hwnd==p->window&&message.message==collect_message){p->navigate();return true;}
    if(message.hwnd==p->window||IsChild(p->window,message.hwnd)||message.hwnd==p->header||IsChild(p->header,message.hwnd))return shortcut(p,message.message,message.wParam,message.lParam);
    return false;
}
void init_browser(){
    VALUE root=rb_define_module("Lunetile"),klass=rb_define_class_under(root,"Browser",rb_cObject);
    rb_define_alloc_func(klass,allocate);rb_define_singleton_method(klass,"available?",RUBY_METHOD_FUNC(available),0);
    rb_define_private_method(klass,"__create",RUBY_METHOD_FUNC(create),4);rb_define_private_method(klass,"__navigate",RUBY_METHOD_FUNC(navigate),1);rb_define_private_method(klass,"__load_file",RUBY_METHOD_FUNC(load_file),1);
    rb_define_private_method(klass,"__rect",RUBY_METHOD_FUNC(get_rect),0);rb_define_private_method(klass,"__set_rect",RUBY_METHOD_FUNC(set_rect),4);rb_define_private_method(klass,"__error",RUBY_METHOD_FUNC(error),0);
    rb_define_method(klass,"reload",RUBY_METHOD_FUNC(reload),0);rb_define_method(klass,"visible",RUBY_METHOD_FUNC(visible),0);rb_define_method(klass,"visible=",RUBY_METHOD_FUNC(set_visible),1);
    rb_define_method(klass,"focus",RUBY_METHOD_FUNC(focus),0);rb_define_method(klass,"blur",RUBY_METHOD_FUNC(blur),0);rb_define_method(klass,"dispose",RUBY_METHOD_FUNC(dispose),0);rb_define_method(klass,"disposed?",RUBY_METHOD_FUNC(disposed),0);rb_define_method(klass,"state",RUBY_METHOD_FUNC(state),0);
}
