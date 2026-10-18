#include <windows.h>
#include <zlib.h>
#include <cstdio>
#include <cstdint>
#include <filesystem>
#include <stdexcept>
#include <string>
#include <vector>
#include "graphics.h"
#include "audio.h"
#include <ruby.h>
#include <ruby/encoding.h>
#include <ruby/version.h>
#include "builtin.h"

void init_rgss_types();
void init_win32_api();
void init_file_io(VALUE module);

namespace {
bool initialized = false;
bool ever_initialized = false;
bool failed = false;
DWORD owner = 0;
std::vector<std::wstring> rtp_paths;
std::string data_encoding = "UTF-8";

void log_line(const std::string& text) {
    FILE* stream = nullptr;
    if (fopen_s(&stream, "rgssxp.log", "ab") == 0 && stream) {
        fwrite(text.data(), 1, text.size(), stream);
        fwrite("\n", 1, 1, stream);
        fclose(stream);
    }
}
std::wstring wide(const char* bytes, UINT codepage) {
    if (!bytes || !*bytes) return {};
    int size = MultiByteToWideChar(codepage, MB_ERR_INVALID_CHARS, bytes, -1, nullptr, 0);
    if (!size) throw std::runtime_error("Invalid path encoding");
    std::wstring result(size, L'\0');
    MultiByteToWideChar(codepage, MB_ERR_INVALID_CHARS, bytes, -1, result.data(), size);
    result.resize(size - 1);
    return result;
}
std::string utf8(const std::wstring& text) {
    int size = WideCharToMultiByte(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
    std::string result(size, '\0');
    WideCharToMultiByte(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), result.data(), size, nullptr, nullptr);
    return result;
}
VALUE error_string(VALUE error) { return rb_funcall(error, rb_intern("full_message"), 0); }
bool ruby_failed(int status) {
    if (!status) return false;
    int formatting = 0;
    VALUE message = rb_protect(error_string, rb_errinfo(), &formatting);
    if (!formatting && RB_TYPE_P(message, T_STRING)) log_line(std::string(RSTRING_PTR(message), RSTRING_LEN(message)));
    else log_line("Ruby exception; full_message could not be formatted");
    rb_set_errinfo(Qnil);
    failed = true;
    return true;
}
VALUE inflate_source(VALUE, VALUE input) {
    StringValue(input);
    const uLong length = static_cast<uLong>(RSTRING_LEN(input));
    uLongf capacity = 4096;
    for (; capacity <= 128 * 1024 * 1024; capacity *= 2) {
        VALUE output = rb_str_new(nullptr, capacity);
        uLongf actual = capacity;
        uLong consumed = length;
        int status = uncompress2(reinterpret_cast<Bytef*>(RSTRING_PTR(output)), &actual,
                                 reinterpret_cast<const Bytef*>(RSTRING_PTR(input)), &consumed);
        RB_GC_GUARD(input);
        if (status == Z_OK) {
            if (consumed != length) rb_raise(rb_eRuntimeError, "Trailing bytes after zlib script");
            rb_str_set_len(output, actual); return output;
        }
        if (status != Z_BUF_ERROR) rb_raise(rb_eRuntimeError, "Invalid zlib script: %s", zError(status));
    }
    rb_raise(rb_eRuntimeError, "Inflated script exceeds 128 MiB");
}
VALUE decode_archive(VALUE, VALUE input, VALUE key_value) {
    StringValue(input);
    uint32_t key = NUM2UINT(key_value);
    long length = RSTRING_LEN(input);
    if (length > 128 * 1024 * 1024) rb_raise(rb_eArgError, "RGSSAD entry exceeds 128 MiB");
    VALUE output = rb_str_new(nullptr, length);
    const auto* source = reinterpret_cast<const unsigned char*>(RSTRING_PTR(input));
    auto* target = reinterpret_cast<unsigned char*>(RSTRING_PTR(output));
    for (long i = 0; i < length; ++i) {
        target[i] = source[i] ^ static_cast<unsigned char>(key >> ((i % 4) * 8));
        if (i % 4 == 3) key = key * 7 + 3;
    }
    RB_GC_GUARD(input);
    return output;
}
// Ruby exceptions remain inside rb_protect; no C++ owner is on the longjmp path.
VALUE evaluate_bootstrap(VALUE) {
    init_file_io(rb_const_get(rb_cObject, rb_intern("RGSSXP")));
    init_rgss_types();
    init_win32_api();
    rb_eval_string(value_types);
    rb_eval_string(data_types);
    rb_eval_string(text_support);
    rb_eval_string(integer_map_support);
    init_bitmap();
    init_graphics();
    rb_eval_string(graphics_support);
    rb_eval_string(rpg_graphics_support);
    init_input();
    init_audio();
    rb_eval_string(audio_support);
    return rb_eval_string(R"RUBY(# encoding: UTF-8
module RGSSXP
  VERSION = '0.1.0'
  def self.run_scripts(path)
    entries = Marshal.load(RGSSXP.read_file(path))
    raise TypeError, 'Scripts must be an Array' unless entries.is_a?(Array)
    $RGSS_SCRIPTS = entries
    entries.each_with_index do |entry, index|
      unless entry.is_a?(Array) && entry.size == 3 && entry[0].is_a?(Integer) && entry[1].is_a?(String) && entry[2].is_a?(String)
        raise TypeError, "Invalid script entry #{index}"
      end
      source = inflate(entry[2])
      source.force_encoding(Encoding::UTF_8)
      raise EncodingError, "Script #{index} requires explicit encoding migration" unless source.valid_encoding?
      eval(source, TOPLEVEL_BINDING, "#{index}:#{entry[1]}", 1)
    end
  end
end
)RUBY");
}
struct ScriptPaths { const char* scripts; long scripts_length; const char* archive; long archive_length; };
VALUE run_scripts(VALUE pointer) {
    const auto* paths = reinterpret_cast<const ScriptPaths*>(pointer);
    VALUE module = rb_const_get(rb_cObject, rb_intern("RGSSXP"));
    VALUE archive = paths->archive_length ? rb_utf8_str_new(paths->archive, paths->archive_length) : Qnil;
    rb_funcall(module, rb_intern("open_archive"), 1, archive);
    VALUE path = rb_utf8_str_new(paths->scripts, paths->scripts_length);
    return rb_funcall(module, rb_intern("run_scripts"), 1, path);
}
VALUE handle_reset(VALUE error) {
    ID name=rb_intern("Reset");
    if(!rb_const_defined_at(rb_cObject,name))return Qfalse;
    VALUE klass=rb_const_get_at(rb_cObject,name);
    if(!RB_TYPE_P(klass,T_CLASS)||!rb_obj_is_kind_of(error,klass))return Qfalse;
    audio_shutdown();
    rb_funcall(rb_const_get(rb_cObject,rb_intern("RGSSXP")),rb_intern("reset_display"),0);
    graphics_reset();
    log_line("Ruby Reset: scripts reloading; globals, Font defaults and frame_count preserved");
    return Qtrue;
}
int finish_ruby(int result) {
    if (!initialized) return result;
    log_line("Ruby finalizing");
    int status = ruby_cleanup(result);
    audio_shutdown();
    graphics_shutdown();
    initialized = false;
    log_line("Ruby finalized");
    return status;
}
}

extern "C" int __cdecl RGSSSetupRTP(const char* ini, char* error, int capacity) {
    try {
        rtp_paths.clear();
        std::wstring ini_path = wide(ini, CP_ACP);
        wchar_t encoding[32]{};
        GetPrivateProfileStringW(L"RGSSXP", L"DataEncoding", L"UTF-8", encoding, 32, ini_path.c_str());
        data_encoding = utf8(encoding);
        if (data_encoding != "UTF-8" && data_encoding != "CP949" && data_encoding != "CP932")
            throw std::runtime_error("Unsupported explicit project data encoding");
        for (int i = 1; i <= 3; ++i) {
            wchar_t name[512]{};
            std::wstring key = L"RTP" + std::to_wstring(i);
            GetPrivateProfileStringW(L"Game", key.c_str(), L"", name, 512, ini_path.c_str());
            if (!*name) continue;
            wchar_t path[32768]{};
            DWORD bytes = sizeof(path);
            LSTATUS status = RegGetValueW(HKEY_LOCAL_MACHINE, L"SOFTWARE\\Enterbrain\\RGSS\\RTP", name,
                RRF_RT_REG_SZ, nullptr, path, &bytes);
            if (status != ERROR_SUCCESS || !std::filesystem::is_directory(path))
                throw std::runtime_error("Configured RTP is not installed: " + utf8(name));
            rtp_paths.emplace_back(path);
        }
        if (error && capacity > 0) error[0] = '\0';
        return 1;
    } catch (const std::exception& e) {
        if (error && capacity > 0) strncpy_s(error, capacity, e.what(), _TRUNCATE);
        log_line(e.what());
        return 0;
    }
}
extern "C" void __cdecl RGSSInitialize(HMODULE) {
    if (ever_initialized) { failed = true; log_line("Repeated Ruby initialization is unsupported"); return; }
    ever_initialized = true;
    owner = GetCurrentThreadId();
    failed = false;
    static char program[] = "RGSSXP";
    static char* arguments[] = {program, nullptr};
    int argc = 1;
    char** argv = arguments;
    ruby_sysinit(&argc, &argv);
    RUBY_INIT_STACK;
    int status = ruby_setup();
    if (status) { failed = true; log_line("ruby_setup failed"); return; }
    initialized = true;
    // ruby_setup alone leaves Ruby's builtin methods (including Marshal.load) private.
    char no_gems[] = "--disable-gems";
    char expression[] = "-e";
    char empty[] = "";
    char* options[] = {program, no_gems, expression, empty, nullptr};
    void* node = ruby_options(4, options);
    if (!ruby_executable_node(node, &status) || ruby_exec_node(node) != 0) {
        failed = true;
        log_line("Ruby builtin initialization failed");
        return;
    }
    ruby_script("RGSSXP");
    VALUE module = rb_define_module("RGSSXP");
    rb_define_const(module, "DATA_ENCODING", rb_obj_freeze(rb_utf8_str_new_cstr(data_encoding.c_str())));
    rb_define_singleton_method(module, "inflate", RUBY_METHOD_FUNC(inflate_source), 1);
    rb_define_singleton_method(module, "decode_archive", RUBY_METHOD_FUNC(decode_archive), 2);
    VALUE rtp = rb_ary_new();
    for (const auto& path : rtp_paths) {
        std::string bytes = utf8(path);
        rb_ary_push(rtp, rb_obj_freeze(rb_utf8_str_new(bytes.data(), static_cast<long>(bytes.size()))));
    }
    rb_define_const(module, "RTP_PATHS", rb_obj_freeze(rtp));
    rb_protect(evaluate_bootstrap, Qnil, &status);
    ruby_failed(status);
    log_line(std::string("Ruby initialized: ") + ruby_description);
}
extern "C" unsigned long __cdecl RGSSEval(const char* source) {
    if (!initialized || failed || GetCurrentThreadId() != owner) return 0;
    int status = 0;
    VALUE result = rb_eval_string_protect(source, &status);
    if (ruby_failed(status)) return 0;
    return static_cast<unsigned long>(result);
}
extern "C" int __cdecl RGSSGameMain(HWND window, const char* scripts, const char* archive) {
    if (GetCurrentThreadId() != owner) return 1;
    if (!initialized || failed) return finish_ruby(1);
    graphics_attach(window);
    int result = 1;
    try {
        std::string path = utf8(wide(scripts, CP_ACP));
        std::string archive_path = utf8(wide(archive, CP_ACP));
        ScriptPaths paths{path.data(), static_cast<long>(path.size()), archive_path.data(), static_cast<long>(archive_path.size())};
        for(;;){
            int status=0;
            rb_protect(run_scripts,reinterpret_cast<VALUE>(&paths),&status);
            if(status){
                VALUE error=rb_errinfo();int reset_status=0;
                rb_set_errinfo(Qnil);
                VALUE reset=rb_protect(handle_reset,error,&reset_status);
                RB_GC_GUARD(error);
                if(reset_status){ruby_failed(reset_status);result=1;break;}
                if(RTEST(reset))continue;
                rb_set_errinfo(error);
            }
            if(status&&rb_obj_is_kind_of(rb_errinfo(),rb_eSystemExit)){
                result=NUM2INT(rb_funcall(rb_errinfo(),rb_intern("status"),0));rb_set_errinfo(Qnil);
            }else result=ruby_failed(status)?1:0;
            break;
        }
    } catch (const std::exception& e) { log_line(e.what()); }
    // This launcher calls RGSSFinalize only from its native exception handler.
    return finish_ruby(result);
}
extern "C" void __cdecl RGSSFinalize(void) {
    if (!initialized || GetCurrentThreadId() != owner) return;
    finish_ruby(failed ? 1 : 0);
}
