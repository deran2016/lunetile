#include <windows.h>
#include <algorithm>
#include <cerrno>
#include <cstdio>
#include <future>
#include <io.h>
#include <memory>
#include <share.h>
#include <stdexcept>
#include <string>
#include <sys/stat.h>
#include <vector>
#include <ruby.h>
#include <ruby/encoding.h>
extern "C" void Init_stringio(void);
extern "C" void ruby_init_ext(const char*, void (*)(void));

namespace {
constexpr unsigned long long read_limit = 128ull * 1024 * 1024;
DWORD last_worker = 0;
unsigned long long read_count = 0;
struct ReadResult {
    std::vector<char> bytes;
    unsigned long long size = 0;
    long long modified = 0;
    DWORD thread = 0;
    int error = 0;
};
ReadResult read_worker(std::wstring path, unsigned long long offset, long long length, long long expected) {
    ReadResult result;
    result.thread = GetCurrentThreadId();
    std::unique_ptr<FILE, decltype(&fclose)> file(_wfsopen(path.c_str(), L"rb", _SH_DENYNO), fclose);
    if (!file) { result.error = errno; return result; }
    struct _stat64 info{};
    if (_fstat64(_fileno(file.get()), &info)) { result.error = errno; return result; }
    if (info.st_size < 0) throw std::runtime_error("Invalid file size");
    result.size = static_cast<unsigned long long>(info.st_size);
    FILE_BASIC_INFO basic{};
    if (!GetFileInformationByHandleEx(reinterpret_cast<HANDLE>(_get_osfhandle(_fileno(file.get()))), FileBasicInfo, &basic, sizeof(basic)))
        throw std::runtime_error("Cannot query file modification time");
    result.modified = basic.LastWriteTime.QuadPart;
    if (expected >= 0 && result.size != static_cast<unsigned long long>(expected))
        throw std::runtime_error("RGSSAD changed after indexing");
    auto available = offset >= result.size ? 0 : result.size - offset;
    auto count = length < 0 ? available : std::min(available, static_cast<unsigned long long>(length));
    if (count > read_limit) throw std::length_error("File read exceeds 128 MiB limit");
    result.bytes.resize(static_cast<size_t>(count));
    if (count && _fseeki64(file.get(), static_cast<long long>(offset), SEEK_SET)) { result.error = errno; return result; }
    size_t done = 0;
    while (done < result.bytes.size()) {
        size_t got = fread(result.bytes.data() + done, 1, std::min<size_t>(1024 * 1024, result.bytes.size() - done), file.get());
        if (!got) {
            if (ferror(file.get())) { result.error = errno ? errno : EIO; return result; }
            throw std::runtime_error("File truncated while reading");
        }
        done += got;
    }
    if (_fstat64(_fileno(file.get()), &info)) { result.error = errno; return result; }
    if (info.st_size < 0 || static_cast<unsigned long long>(info.st_size) != result.size)
        throw std::runtime_error("File changed while reading");
    return result;
}
VALUE pack_result(VALUE pointer) {
    auto* result = reinterpret_cast<const ReadResult*>(pointer);
    VALUE size = ULL2NUM(result->size);
    VALUE bytes = rb_str_new(result->bytes.data(), static_cast<long>(result->bytes.size()));
    long long ticks = result->modified - 116444736000000000LL;
    long long seconds = ticks / 10000000, fraction = ticks % 10000000;
    if (fraction < 0) { --seconds; fraction += 10000000; }
    VALUE modified = rb_time_nano_new(static_cast<time_t>(seconds), static_cast<long>(fraction * 100));
    VALUE packed = rb_ary_new_from_args(3, bytes, size, modified);
    RB_GC_GUARD(modified);
    RB_GC_GUARD(bytes); RB_GC_GUARD(size);
    return packed;
}
VALUE read_disk(VALUE, VALUE path, VALUE offset_value, VALUE length_value, VALUE expected_value) {
    StringValue(path);
    VALUE encoded = rb_str_export_to_enc(path, rb_utf8_encoding());
    auto offset = NUM2ULL(offset_value);
    long long length = NIL_P(length_value) ? -1 : NUM2LL(length_value);
    long long expected = NIL_P(expected_value) ? -1 : NUM2LL(expected_value);
    if (offset > LLONG_MAX || (!NIL_P(length_value) && (length < 0 || length > read_limit)) ||
        (!NIL_P(expected_value) && expected < 0)) rb_raise(rb_eArgError, "Invalid file read range");
    const char* name = StringValueCStr(encoded);
    char error[256]{};
    bool argument_error = false, out_of_memory = false;
    int syscall_error = 0, ruby_state = 0;
    VALUE packed = Qnil;
    {
        try {
            int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, name, -1, nullptr, 0);
            if (!count) throw std::runtime_error("Invalid file path encoding");
            std::wstring wide(count, L'\0');
            MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, name, -1, wide.data(), count);
            wide.resize(count - 1);
            std::replace(wide.begin(), wide.end(), L'/', L'\\');
            if (wide.size() >= 3 && wide[1] == L':' && wide[2] == L'\\') wide = L"\\\\?\\" + wide;
            else if (wide.rfind(L"\\\\", 0) == 0 && wide.rfind(L"\\\\?\\", 0) != 0) wide = L"\\\\?\\UNC\\" + wide.substr(2);
            // shortcut: one native task per cache miss; use a persistent worker if profiling shows task creation dominates.
            auto result = std::async(std::launch::async, read_worker, std::move(wide), offset, length, expected).get();
            if (result.thread == GetCurrentThreadId()) throw std::runtime_error("File I/O did not leave the Ruby thread");
            last_worker = result.thread; ++read_count;
            syscall_error = result.error;
            if (!syscall_error) packed = rb_protect(pack_result, reinterpret_cast<VALUE>(&result), &ruby_state);
        } catch (const std::bad_alloc&) { out_of_memory = true;
        } catch (const std::length_error& e) { argument_error = true; sprintf_s(error, "%s", e.what());
        } catch (const std::exception& e) { sprintf_s(error, "%s", e.what()); }
    }
    RB_GC_GUARD(encoded);
    // Ruby can longjmp; release all C++ owners before propagating any exception.
    if (ruby_state) rb_jump_tag(ruby_state);
    if (out_of_memory) rb_memerror();
    if (syscall_error) rb_syserr_fail_str(syscall_error, path);
    if (*error) rb_raise(argument_error ? rb_eArgError : rb_eIOError, "%s", error);
    return packed;
}
VALUE io_threads(VALUE) {
    return rb_ary_new_from_args(3, ULONG2NUM(GetCurrentThreadId()), ULONG2NUM(last_worker), ULL2NUM(read_count));
}
}
void init_file_io(VALUE module) {
    ruby_init_ext("stringio.so", Init_stringio);
    rb_require("stringio");
    rb_define_singleton_method(module, "read_disk", RUBY_METHOD_FUNC(read_disk), 4);
    rb_define_singleton_method(module, "__io_threads", RUBY_METHOD_FUNC(io_threads), 0);
}
