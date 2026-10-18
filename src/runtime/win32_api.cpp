#include <windows.h>
#include <cstdint>
#include <cstring>
#include <ruby.h>
#include <ruby/encoding.h>

namespace {
struct Api {
    HMODULE module;
    FARPROC function;
    char arguments[16];
    int count;
    char result;
};
void api_free(void* pointer) {
    auto* api = static_cast<Api*>(pointer);
    if (api->module) FreeLibrary(api->module);
    ruby_xfree(api);
}
size_t api_size(const void*) { return sizeof(Api); }
const rb_data_type_t api_type = {"RGSSXP::Win32API", {nullptr, api_free, api_size}, nullptr, nullptr, RUBY_TYPED_FREE_IMMEDIATELY};
Api* get_api(VALUE self) {
    Api* api;
    TypedData_Get_Struct(self, Api, &api_type, api);
    return api;
}
VALUE api_alloc(VALUE klass) { return TypedData_Wrap_Struct(klass, &api_type, ruby_xcalloc(1, sizeof(Api))); }
char type_code(VALUE value) {
    StringValue(value);
    if (RSTRING_LEN(value) != 1) rb_raise(rb_eArgError, "Win32API type must be one character");
    char type = RSTRING_PTR(value)[0];
    if (type >= 'a' && type <= 'z') type -= 'a' - 'A';
    if (type != 'I' && type != 'L' && type != 'P' && type != 'V')
        rb_raise(rb_eNotImpError, "Unsupported Win32API type: %c", type);
    return type;
}
VALUE api_init(VALUE self, VALUE library, VALUE name, VALUE arguments, VALUE result) {
    auto* api = get_api(self);
    if (api->module) rb_raise(rb_eRuntimeError, "Win32API object is already initialized");
    StringValue(library); StringValue(name);
    if (RSTRING_LEN(name) < 1 || RSTRING_LEN(name) > 1024 || RSTRING_LEN(library) > 32767)
        rb_raise(rb_eArgError, "Invalid Win32API library/function name length");
    if (RB_TYPE_P(arguments, T_ARRAY)) {
        if (RARRAY_LEN(arguments) > 16) rb_raise(rb_eArgError, "At most 16 Win32API arguments supported");
        api->count = static_cast<int>(RARRAY_LEN(arguments));
        for (int i = 0; i < api->count; ++i) api->arguments[i] = type_code(rb_ary_entry(arguments, i));
    } else {
        StringValue(arguments);
        if (RSTRING_LEN(arguments) > 16) rb_raise(rb_eArgError, "At most 16 Win32API arguments supported");
        api->count = static_cast<int>(RSTRING_LEN(arguments));
        for (int i = 0; i < api->count; ++i) api->arguments[i] = type_code(rb_str_substr(arguments, i, 1));
    }
    if (api->count == 1 && api->arguments[0] == 'V') api->count = 0;
    for (int i = 0; i < api->count; ++i)
        if (api->arguments[i] == 'V') rb_raise(rb_eArgError, "Void cannot be combined with Win32API arguments");
    api->result = type_code(result);
    VALUE unicode = rb_str_encode(library, rb_enc_from_encoding(rb_utf8_encoding()), 0, Qnil);
    const char* bytes = StringValueCStr(unicode);
    int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, bytes, -1, nullptr, 0);
    if (!length) rb_raise(rb_eArgError, "Invalid Win32API library path");
    VALUE buffer = rb_str_new(nullptr, length * sizeof(wchar_t));
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, bytes, -1, reinterpret_cast<wchar_t*>(RSTRING_PTR(buffer)), length);
    api->module = LoadLibraryW(reinterpret_cast<const wchar_t*>(RSTRING_PTR(buffer)));
    RB_GC_GUARD(unicode); RB_GC_GUARD(buffer);
    if (!api->module) rb_raise(rb_eLoadError, "Cannot load Win32API library (Windows error %lu)", GetLastError());
    const char* function = StringValueCStr(name);
    api->function = GetProcAddress(api->module, function);
    if (!api->function) rb_raise(rb_eLoadError, "Cannot find Win32API function: %s", function);
    return self;
}
// Restore ESP explicitly: legacy Win32API accepts both stdcall and cdecl exports.
__declspec(noinline) DWORD invoke(FARPROC function, const DWORD* arguments, int count) {
    DWORD result, saved_stack;
    __asm {
        mov saved_stack, esp
        mov ecx, count
        mov edx, arguments
    push_argument:
        test ecx, ecx
        jz call_function
        dec ecx
        push dword ptr [edx + ecx * 4]
        jmp push_argument
    call_function:
        call function
        mov result, eax
        mov esp, saved_stack
    }
    return result;
}
VALUE api_call(int argc, VALUE* argv, VALUE self) {
    auto* api = get_api(self);
    if (!api->function) rb_raise(rb_eRuntimeError, "Uninitialized Win32API object");
    rb_check_arity(argc, api->count, api->count);
    DWORD arguments[16]{};
    for (int i = 0; i < argc; ++i) {
        if (api->arguments[i] == 'P') {
            if (RB_INTEGER_TYPE_P(argv[i]) && NUM2LONG(argv[i]) == 0) arguments[i] = 0;
            else {
                Check_Type(argv[i], T_STRING);
                rb_str_modify(argv[i]);
            }
        } else arguments[i] = NUM2ULONG(argv[i]);
    }
    // Collect pointers only after every potentially allocating conversion has finished.
    for (int i = 0; i < argc; ++i)
        if (api->arguments[i] == 'P' && RB_TYPE_P(argv[i], T_STRING))
            arguments[i] = reinterpret_cast<DWORD>(RSTRING_PTR(argv[i]));
    DWORD bits = invoke(api->function, arguments, argc);
    if (api->result == 'V') return INT2FIX(0);
    if (api->result == 'P') return bits ? rb_str_new_cstr(reinterpret_cast<const char*>(bits)) : Qnil;
    return LONG2NUM(static_cast<LONG>(bits));
}
}

void init_win32_api() {
    VALUE klass = rb_define_class("Win32API", rb_cObject);
    rb_define_alloc_func(klass, api_alloc);
    rb_define_method(klass, "initialize", RUBY_METHOD_FUNC(api_init), 4);
    rb_define_method(klass, "call", RUBY_METHOD_FUNC(api_call), -1);
}
