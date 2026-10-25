#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <winhttp.h>
#define SECURITY_WIN32
#include <security.h>
#include <winternl.h>
#define SCHANNEL_USE_BLACKLISTS
#include <schannel.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstring>
#include <deque>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include <ruby.h>
#include <ruby/encoding.h>
#include "network.h"
// Ruby's Windows headers replace Winsock calls with Ruby/CRT descriptor wrappers.
#undef socket
#undef connect
#undef send
#undef recv
#undef getsockopt
#undef setsockopt
#undef ioctlsocket

namespace {
using Clock = std::chrono::steady_clock;
constexpr size_t MiB = 1024 * 1024;
enum State { Pending, Succeeded, Failed, Cancelled, Connecting, Open, Closed };
const char* state_names[] = {"pending", "succeeded", "failed", "cancelled", "connecting", "open", "closed"};
ID state_ids[7]{};
bool finalizing = false;
struct Failure { const char* code; unsigned long native = 0; };
[[noreturn]] void fail(const char* code, unsigned long native = 0) { throw Failure{code, native}; }
std::wstring wide(const std::string& text) {
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(), static_cast<int>(text.size()), nullptr, 0);
    if (!count && !text.empty()) fail("argument");
    std::wstring result(count, L'\0');
    if (count) MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text.data(), static_cast<int>(text.size()), result.data(), count);
    return result;
}
std::string utf8(const std::wstring& text) {
    int count = WideCharToMultiByte(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), nullptr, 0, nullptr, nullptr);
    std::string result(count, '\0');
    if (count) WideCharToMultiByte(CP_UTF8, 0, text.data(), static_cast<int>(text.size()), result.data(), count, nullptr, nullptr);
    return result;
}
struct Job {
    const bool http;
    const Clock::time_point started = Clock::now();
    std::atomic<State> state;
    std::atomic<bool> stop{false}, done{false};
    std::mutex mutex;
    std::thread worker;
    const char* error = nullptr;
    unsigned long native_error = 0;
    explicit Job(bool is_http) : http(is_http), state(is_http ? Pending : Connecting) {}
    virtual ~Job() { if (worker.joinable()) worker.join(); }
    virtual void work() = 0;
    bool cancel() {
        std::lock_guard<std::mutex> lock(mutex);
        State current = state.load();
        if (current != Pending && current != Connecting && current != Open) return false;
        state = http ? Cancelled : Closed;
        stop = true;
        return true;
    }
    void check(Clock::time_point deadline) {
        if (stop) fail("cancelled");
        if (Clock::now() >= deadline) fail("timeout");
    }
    void run() noexcept {
        try { work(); }
        catch (Failure e) { finish_error(e.code, e.native); }
        catch (const std::bad_alloc&) { finish_error("memory", 0); }
        catch (...) { finish_error("io", 0); }
        done = true;
    }
    void finish_error(const char* code, unsigned long native) {
        std::lock_guard<std::mutex> lock(mutex);
        if (!stop) { error = code; native_error = native; state = Failed; }
    }
};
std::vector<std::shared_ptr<Job>> jobs;
void reap() {
    jobs.erase(std::remove_if(jobs.begin(), jobs.end(), [](const auto& job) {
        if (!job->done) return false;
        if (job->worker.joinable()) job->worker.join();
        return true;
    }), jobs.end());
}
void launch(const std::shared_ptr<Job>& job) {
    reap();
    if (std::count_if(jobs.begin(), jobs.end(), [&](const auto& other) { return other->http == job->http; }) >= 8) fail("limit");
    jobs.push_back(job);
    try { job->worker = std::thread([job] { job->run(); }); }
    catch (...) { jobs.pop_back(); throw; }
}

struct InternetHandle {
    HINTERNET value = nullptr;
    ~InternetHandle() { if (value) WinHttpCloseHandle(value); }
};
const char* http_error(DWORD code) {
    if (code == ERROR_WINHTTP_TIMEOUT) return "timeout";
    if (code == ERROR_WINHTTP_NAME_NOT_RESOLVED) return "dns";
    if (code == ERROR_WINHTTP_CANNOT_CONNECT || code == ERROR_WINHTTP_CONNECTION_ERROR) return "connect";
    if (code == ERROR_WINHTTP_SECURE_FAILURE || code == ERROR_WINHTTP_CLIENT_AUTH_CERT_NEEDED) return "tls";
    if (code == ERROR_WINHTTP_HEADER_SIZE_OVERFLOW || code == ERROR_WINHTTP_RESPONSE_DRAIN_OVERFLOW) return "limit";
    return "http";
}
struct HttpJob : Job {
    std::wstring method, host, path, headers;
    std::string body, response_headers, response_body;
    INTERNET_PORT port = 0;
    bool secure = false;
    DWORD status = 0;
    int timeout;
    std::mutex event_mutex;
    std::condition_variable event;
    DWORD notification = 0, transferred = 0, operation_error = 0;
    bool handle_closed = false;
    HttpJob(std::string verb, std::string url, std::string lines, std::string data, int milliseconds) : Job(true), timeout(milliseconds) {
        if (url.empty() || url.size() > 8192 || lines.size() > 65536 || data.size() > MiB ||
            url.find('\0') != std::string::npos || lines.find('\0') != std::string::npos) fail("argument");
        method = wide(verb); headers = wide(lines); body = std::move(data);
        std::wstring address = wide(url);
        URL_COMPONENTS parts{}; parts.dwStructSize = sizeof(parts);
        parts.dwSchemeLength = parts.dwHostNameLength = parts.dwUrlPathLength = parts.dwExtraInfoLength = parts.dwUserNameLength = parts.dwPasswordLength = static_cast<DWORD>(-1);
        if (!WinHttpCrackUrl(address.c_str(), static_cast<DWORD>(address.size()), 0, &parts) ||
            (parts.nScheme != INTERNET_SCHEME_HTTP && parts.nScheme != INTERNET_SCHEME_HTTPS) || !parts.dwHostNameLength ||
            parts.dwUserNameLength || parts.dwPasswordLength || address.find(L'#') != std::wstring::npos) fail("argument");
        host.assign(parts.lpszHostName, parts.dwHostNameLength); port = parts.nPort; secure = parts.nScheme == INTERNET_SCHEME_HTTPS;
        path.assign(parts.lpszUrlPath, parts.dwUrlPathLength);
        if (path.empty()) path = L"/";
        if (parts.dwExtraInfoLength) path.append(parts.lpszExtraInfo, parts.dwExtraInfoLength);
    }
    static void CALLBACK callback(HINTERNET, DWORD_PTR context, DWORD flag, void* info, DWORD length) noexcept {
        auto* self = reinterpret_cast<HttpJob*>(context);
        if (!self) return;
        std::lock_guard<std::mutex> lock(self->event_mutex);
        if (flag == WINHTTP_CALLBACK_STATUS_HANDLE_CLOSING) self->handle_closed = true;
        else if (flag == WINHTTP_CALLBACK_STATUS_SENDREQUEST_COMPLETE || flag == WINHTTP_CALLBACK_STATUS_HEADERS_AVAILABLE ||
                 flag == WINHTTP_CALLBACK_STATUS_READ_COMPLETE || flag == WINHTTP_CALLBACK_STATUS_REQUEST_ERROR) {
            self->notification = flag;
            self->transferred = length;
            if (flag == WINHTTP_CALLBACK_STATUS_REQUEST_ERROR && info && length >= sizeof(WINHTTP_ASYNC_RESULT))
                self->operation_error = reinterpret_cast<WINHTTP_ASYNC_RESULT*>(info)->dwError;
        }
        self->event.notify_all();
    }
    DWORD wait(DWORD expected, Clock::time_point deadline) {
        std::unique_lock<std::mutex> lock(event_mutex);
        for (;;) {
            check(deadline);
            if (operation_error) fail(http_error(operation_error), operation_error);
            if (notification == expected) { notification = 0; return transferred; }
            event.wait_until(lock, std::min(deadline, Clock::now() + std::chrono::milliseconds(20)));
        }
    }
    static void checked(BOOL ok) { if (!ok) { DWORD code = GetLastError(); if (code != ERROR_IO_PENDING) fail(http_error(code), code); } }
    static void option(HINTERNET handle, DWORD name, DWORD value) {
        if (!WinHttpSetOption(handle, name, &value, sizeof(value))) fail("http", GetLastError());
    }
    void work() override {
        auto deadline = started + std::chrono::milliseconds(timeout);
        check(deadline);
        InternetHandle session, connection;
        session.value = WinHttpOpen(L"Lunetile/0.1", WINHTTP_ACCESS_TYPE_NO_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, WINHTTP_FLAG_ASYNC);
        if (!session.value) fail("http", GetLastError());
        checked(WinHttpSetTimeouts(session.value, timeout, timeout, timeout, timeout));
        option(session.value, WINHTTP_OPTION_SECURE_PROTOCOLS, WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_2 | WINHTTP_FLAG_SECURE_PROTOCOL_TLS1_3);
        connection.value = WinHttpConnect(session.value, host.c_str(), port, 0);
        if (!connection.value) fail("connect", GetLastError());
        std::vector<char> buffer(65536);
        HINTERNET request = WinHttpOpenRequest(connection.value, method.c_str(), path.c_str(), nullptr, WINHTTP_NO_REFERER,
            WINHTTP_DEFAULT_ACCEPT_TYPES, secure ? WINHTTP_FLAG_SECURE : 0);
        if (!request) fail("http", GetLastError());
        bool callback_set = false;
        try {
            DWORD_PTR context = reinterpret_cast<DWORD_PTR>(this);
            if (!WinHttpSetOption(request, WINHTTP_OPTION_CONTEXT_VALUE, &context, sizeof(context))) fail("http", GetLastError());
            if (WinHttpSetStatusCallback(request, callback, WINHTTP_CALLBACK_FLAG_ALL_COMPLETIONS | WINHTTP_CALLBACK_FLAG_HANDLES, 0) == WINHTTP_INVALID_STATUS_CALLBACK)
                fail("http", GetLastError());
            callback_set = true;
            option(request, WINHTTP_OPTION_DISABLE_FEATURE, WINHTTP_DISABLE_REDIRECTS | WINHTTP_DISABLE_COOKIES | WINHTTP_DISABLE_AUTHENTICATION);
            option(request, WINHTTP_OPTION_AUTOLOGON_POLICY, WINHTTP_AUTOLOGON_SECURITY_LEVEL_HIGH);
            option(request, WINHTTP_OPTION_MAX_RESPONSE_HEADER_SIZE, 65536);
            option(request, WINHTTP_OPTION_DECOMPRESSION, WINHTTP_DECOMPRESSION_FLAG_ALL);
            checked(WinHttpSendRequest(request, headers.c_str(), static_cast<DWORD>(headers.size()),
                body.empty() ? WINHTTP_NO_REQUEST_DATA : body.data(), static_cast<DWORD>(body.size()), static_cast<DWORD>(body.size()), context));
            wait(WINHTTP_CALLBACK_STATUS_SENDREQUEST_COMPLETE, deadline);
            checked(WinHttpReceiveResponse(request, nullptr));
            wait(WINHTTP_CALLBACK_STATUS_HEADERS_AVAILABLE, deadline);
            DWORD size = sizeof(status);
            checked(WinHttpQueryHeaders(request, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER, WINHTTP_HEADER_NAME_BY_INDEX, &status, &size, WINHTTP_NO_HEADER_INDEX));
            size = 0;
            if (WinHttpQueryHeaders(request, WINHTTP_QUERY_RAW_HEADERS_CRLF, WINHTTP_HEADER_NAME_BY_INDEX, nullptr, &size, WINHTTP_NO_HEADER_INDEX) || GetLastError() != ERROR_INSUFFICIENT_BUFFER)
                fail("http", GetLastError());
            if (size > 128 * 1024) fail("limit");
            std::wstring raw(size / sizeof(wchar_t), L'\0');
            checked(WinHttpQueryHeaders(request, WINHTTP_QUERY_RAW_HEADERS_CRLF, WINHTTP_HEADER_NAME_BY_INDEX, raw.data(), &size, WINHTTP_NO_HEADER_INDEX));
            while (!raw.empty() && !raw.back()) raw.pop_back();
            response_headers = utf8(raw);
            if (response_headers.size() > 65536) fail("limit");
            std::string received;
            for (;;) {
                check(deadline);
                checked(WinHttpReadData(request, buffer.data(), static_cast<DWORD>(buffer.size()), nullptr));
                DWORD count = wait(WINHTTP_CALLBACK_STATUS_READ_COMPLETE, deadline);
                if (!count) break;
                if (count > buffer.size() || count > 4 * MiB - received.size()) fail("limit");
                received.append(buffer.data(), count);
            }
            {
                std::lock_guard<std::mutex> lock(mutex);
                if (!stop) { response_body = std::move(received); state = Succeeded; }
            }
        } catch (...) {
            close_request(request, callback_set);
            throw;
        }
        close_request(request, callback_set);
        body.clear();
    }
    void close_request(HINTERNET request, bool callback_set) {
        WinHttpCloseHandle(request);
        if (callback_set) {
            // HANDLE_CLOSING is the final callback; its context must outlive pending I/O.
            std::unique_lock<std::mutex> lock(event_mutex);
            event.wait(lock, [&] { return handle_closed; });
        }
    }
};

struct SocketHandle {
    SOCKET value = INVALID_SOCKET;
    ~SocketHandle() { if (value != INVALID_SOCKET) closesocket(value); }
    void reset() { if (value != INVALID_SOCKET) closesocket(value); value = INVALID_SOCKET; }
};
struct EventHandle {
    HANDLE value = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    ~EventHandle() { if (value) CloseHandle(value); }
};
struct AddressList {
    PADDRINFOEXW value = nullptr;
    ~AddressList() { if (value) FreeAddrInfoExW(value); }
};
bool winsock_started = false;
void start_winsock() {
    if (winsock_started) return;
    WSADATA data{};
    int status = WSAStartup(MAKEWORD(2, 2), &data);
    if (status) fail("connect", status);
    winsock_started = true;
}
bool ready(Job& job, SOCKET socket, short events, Clock::time_point deadline) {
    job.check(deadline);
    WSAPOLLFD entry{socket, events, 0};
    int result = WSAPoll(&entry, 1, 20);
    if (result == SOCKET_ERROR) fail("io", WSAGetLastError());
    return result > 0;
}
void send_all(Job& job, SOCKET socket, const char* data, size_t count, Clock::time_point deadline) {
    while (count) {
        job.check(deadline);
        int sent = send(socket, data, static_cast<int>(count), 0);
        if (sent > 0) { data += sent; count -= sent; }
        else if (sent == SOCKET_ERROR && WSAGetLastError() == WSAEWOULDBLOCK) ready(job, socket, POLLWRNORM, deadline);
        else fail("io", sent == SOCKET_ERROR ? WSAGetLastError() : 0);
    }
}
void receive_cipher(Job& job, SOCKET socket, std::vector<char>& bytes, Clock::time_point deadline) {
    char buffer[16384];
    for (;;) {
        job.check(deadline);
        int got = recv(socket, buffer, sizeof(buffer), 0);
        if (got > 0) {
            if (bytes.size() + got > MiB) fail("limit");
            bytes.insert(bytes.end(), buffer, buffer + got);
            return;
        }
        if (!got) fail("tls");
        if (WSAGetLastError() != WSAEWOULDBLOCK) fail("io", WSAGetLastError());
        ready(job, socket, POLLRDNORM, deadline);
    }
}
void keep_extra(std::vector<char>& bytes, SecBuffer* buffers, size_t count) {
    size_t extra = 0;
    for (size_t i = 0; i < count; ++i) if (buffers[i].BufferType == SECBUFFER_EXTRA) extra = buffers[i].cbBuffer;
    if (extra > bytes.size()) fail("tls");
    bytes.erase(bytes.begin(), bytes.end() - extra);
}
struct TlsContext {
    CredHandle credential{};
    CtxtHandle context{};
    bool credential_valid = false, context_valid = false;
    SecPkgContext_StreamSizes sizes{};
    TlsContext() { SecInvalidateHandle(&credential); SecInvalidateHandle(&context); }
    ~TlsContext() {
        if (context_valid) DeleteSecurityContext(&context);
        if (credential_valid) FreeCredentialsHandle(&credential);
    }
    void handshake(Job& job, SOCKET socket, const std::wstring& host, std::vector<char>& incoming, Clock::time_point deadline) {
        if (!credential_valid) {
            SCH_CREDENTIALS credentials{};
            credentials.dwVersion = SCH_CREDENTIALS_VERSION;
            credentials.dwFlags = SCH_CRED_AUTO_CRED_VALIDATION | SCH_CRED_NO_DEFAULT_CREDS;
            TLS_PARAMETERS parameters{};
            parameters.grbitDisabledProtocols = SP_PROT_SSL2 | SP_PROT_SSL3 | SP_PROT_TLS1_0 | SP_PROT_TLS1_1;
            credentials.cTlsParameters = 1; credentials.pTlsParameters = &parameters;
            SECURITY_STATUS result = AcquireCredentialsHandleW(nullptr, const_cast<wchar_t*>(UNISP_NAME_W), SECPKG_CRED_OUTBOUND,
                nullptr, &credentials, nullptr, nullptr, &credential, nullptr);
            if (result != SEC_E_OK) fail("tls", result);
            credential_valid = true;
        }
        for (;;) {
            job.check(deadline);
            SecBuffer input[2]{{static_cast<unsigned long>(incoming.size()), SECBUFFER_TOKEN, incoming.data()}, {0, SECBUFFER_EMPTY, nullptr}};
            SecBufferDesc input_desc{SECBUFFER_VERSION, 2, input};
            struct Output {
                SecBuffer buffers[2]{{0, SECBUFFER_TOKEN, nullptr}, {0, SECBUFFER_ALERT, nullptr}};
                ~Output() { for (auto& buffer : buffers) if (buffer.pvBuffer) FreeContextBuffer(buffer.pvBuffer); }
            } output;
            SecBufferDesc output_desc{SECBUFFER_VERSION, 2, output.buffers};
            ULONG attributes = 0;
            SECURITY_STATUS result = InitializeSecurityContextW(&credential, context_valid ? &context : nullptr,
                const_cast<wchar_t*>(host.c_str()), ISC_REQ_ALLOCATE_MEMORY | ISC_REQ_STREAM | ISC_REQ_CONFIDENTIALITY |
                ISC_REQ_SEQUENCE_DETECT | ISC_REQ_REPLAY_DETECT | ISC_REQ_USE_SUPPLIED_CREDS, 0, 0,
                context_valid ? &input_desc : nullptr, 0, &context, &output_desc, &attributes, nullptr);
            context_valid = SecIsValidHandle(&context);
            if (result == SEC_E_INCOMPLETE_MESSAGE) { receive_cipher(job, socket, incoming, deadline); continue; }
            if (result != SEC_E_OK && result != SEC_I_CONTINUE_NEEDED) fail("tls", result);
            if (output.buffers[0].cbBuffer)
                send_all(job, socket, static_cast<const char*>(output.buffers[0].pvBuffer), output.buffers[0].cbBuffer, deadline);
            keep_extra(incoming, input, 2);
            if (result == SEC_E_OK) {
                if (!(attributes & ISC_RET_CONFIDENTIALITY) || QueryContextAttributesW(&context, SECPKG_ATTR_STREAM_SIZES, &sizes) != SEC_E_OK ||
                    !sizes.cbMaximumMessage || sizes.cbMaximumMessage > 65536) fail("tls");
                return;
            }
            if (incoming.empty()) receive_cipher(job, socket, incoming, deadline);
        }
    }
    std::vector<char> encode(const std::string& plain) {
        std::vector<char> record(sizes.cbHeader + plain.size() + sizes.cbTrailer);
        memcpy(record.data() + sizes.cbHeader, plain.data(), plain.size());
        SecBuffer buffers[4]{{sizes.cbHeader, SECBUFFER_STREAM_HEADER, record.data()},
            {static_cast<unsigned long>(plain.size()), SECBUFFER_DATA, record.data() + sizes.cbHeader},
            {sizes.cbTrailer, SECBUFFER_STREAM_TRAILER, record.data() + sizes.cbHeader + plain.size()}, {0, SECBUFFER_EMPTY, nullptr}};
        SecBufferDesc message{SECBUFFER_VERSION, 4, buffers};
        SECURITY_STATUS result = EncryptMessage(&context, 0, &message, 0);
        if (result != SEC_E_OK) fail("tls", result);
        record.resize(buffers[0].cbBuffer + buffers[1].cbBuffer + buffers[2].cbBuffer);
        return record;
    }
};
struct TcpJob : Job {
    std::wstring host;
    int port, timeout;
    bool tls;
    struct Write { std::string bytes; size_t offset = 0; Clock::time_point deadline; };
    std::deque<Write> writes;
    std::string received;
    size_t queued = 0;
    TcpJob(std::string name, int service, bool secure, int milliseconds) : Job(false), host(wide(name)), port(service), timeout(milliseconds), tls(secure) {}
    void connect_socket(SocketHandle& socket, Clock::time_point deadline) {
        AddressList addresses;
        EventHandle event;
        if (!event.value) fail("dns", GetLastError());
        OVERLAPPED operation{}; operation.hEvent = event.value;
        ADDRINFOEXW hints{}; hints.ai_family = AF_UNSPEC; hints.ai_socktype = SOCK_STREAM; hints.ai_protocol = IPPROTO_TCP;
        HANDLE cancel = nullptr;
        std::wstring service = std::to_wstring(port);
        int result = GetAddrInfoExW(host.c_str(), service.c_str(), NS_ALL, nullptr, &hints, &addresses.value, nullptr, &operation, nullptr, &cancel);
        if (result == WSA_IO_PENDING) {
            try {
                while (WaitForSingleObject(event.value, 20) == WAIT_TIMEOUT) check(deadline);
                result = GetAddrInfoExOverlappedResult(&operation);
            } catch (...) {
                GetAddrInfoExCancel(&cancel);
                WaitForSingleObject(event.value, INFINITE);
                throw;
            }
        }
        if (result) fail("dns", result);
        unsigned long last_error = WSAECONNREFUSED;
        for (auto* address = addresses.value; address; address = address->ai_next) {
            check(deadline);
            socket.reset();
            socket.value = ::socket(address->ai_family, address->ai_socktype, address->ai_protocol);
            if (socket.value == INVALID_SOCKET) { last_error = WSAGetLastError(); continue; }
            u_long nonblocking = 1;
            if (ioctlsocket(socket.value, FIONBIO, &nonblocking)) fail("connect", WSAGetLastError());
            int connected = ::connect(socket.value, address->ai_addr, static_cast<int>(address->ai_addrlen));
            if (!connected) return;
            last_error = WSAGetLastError();
            if (last_error != WSAEWOULDBLOCK && last_error != WSAEINPROGRESS) continue;
            while (!ready(*this, socket.value, POLLWRNORM, deadline)) {}
            int socket_error = 0, size = sizeof(socket_error);
            if (getsockopt(socket.value, SOL_SOCKET, SO_ERROR, reinterpret_cast<char*>(&socket_error), &size)) socket_error = WSAGetLastError();
            if (!socket_error) return;
            last_error = socket_error;
        }
        fail("connect", last_error);
    }
    void work() override {
        auto deadline = started + std::chrono::milliseconds(timeout);
        SocketHandle socket;
        connect_socket(socket, deadline);
        const BOOL no_delay = TRUE;
        if (setsockopt(socket.value, IPPROTO_TCP, TCP_NODELAY, reinterpret_cast<const char*>(&no_delay), sizeof(no_delay))) fail("connect", WSAGetLastError());
        TlsContext security;
        std::vector<char> cipher;
        if (tls) security.handshake(*this, socket.value, host, cipher, deadline);
        {
            std::lock_guard<std::mutex> lock(mutex);
            if (stop) return;
            state = Open;
        }
        std::vector<char> pending;
        size_t pending_offset = 0, pending_plain = 0;
        Clock::time_point send_deadline{};
        for (;;) {
            if (stop) return;
            std::string outgoing;
            size_t available;
            {
                std::lock_guard<std::mutex> lock(mutex);
                if (pending.empty() && !writes.empty()) {
                    const auto& front = writes.front();
                    outgoing = front.bytes.substr(front.offset, std::min<size_t>(16384, tls ? security.sizes.cbMaximumMessage : 16384));
                    send_deadline = front.deadline;
                }
                available = MiB - received.size();
            }
            if (!outgoing.empty()) {
                pending_plain = outgoing.size(); pending_offset = 0;
                if (tls) pending = security.encode(outgoing);
                else pending.assign(outgoing.begin(), outgoing.end());
            }
            if (!pending.empty()) {
                check(send_deadline);
                int sent = send(socket.value, pending.data() + pending_offset, static_cast<int>(pending.size() - pending_offset), 0);
                if (sent > 0) pending_offset += sent;
                else if (sent != SOCKET_ERROR || WSAGetLastError() != WSAEWOULDBLOCK) fail("io", sent == SOCKET_ERROR ? WSAGetLastError() : 0);
                if (pending_offset == pending.size()) {
                    std::lock_guard<std::mutex> lock(mutex);
                    queued -= pending_plain;
                    auto& front = writes.front(); front.offset += pending_plain;
                    if (front.offset == front.bytes.size()) writes.pop_front();
                    pending.clear();
                }
            }
            bool can_receive = available >= (tls ? 65536u : 1u);
            if (can_receive && tls && !cipher.empty()) {
                SecBuffer buffers[4]{{static_cast<unsigned long>(cipher.size()), SECBUFFER_DATA, cipher.data()},
                    {0, SECBUFFER_EMPTY, nullptr}, {0, SECBUFFER_EMPTY, nullptr}, {0, SECBUFFER_EMPTY, nullptr}};
                SecBufferDesc message{SECBUFFER_VERSION, 4, buffers};
                SECURITY_STATUS result = DecryptMessage(&security.context, &message, 0, nullptr);
                if (result == SEC_I_CONTEXT_EXPIRED) { state = Closed; return; }
                if (result == SEC_I_RENEGOTIATE) {
                    keep_extra(cipher, buffers, 4);
                    security.handshake(*this, socket.value, host, cipher, Clock::now() + std::chrono::milliseconds(timeout));
                    continue;
                }
                if (result != SEC_E_INCOMPLETE_MESSAGE) {
                    if (result != SEC_E_OK) fail("tls", result);
                    for (auto& buffer : buffers) if (buffer.BufferType == SECBUFFER_DATA && buffer.cbBuffer) {
                        std::lock_guard<std::mutex> lock(mutex);
                        if (buffer.cbBuffer > MiB - received.size()) fail("limit");
                        received.append(static_cast<const char*>(buffer.pvBuffer), buffer.cbBuffer);
                    }
                    keep_extra(cipher, buffers, 4);
                    continue;
                }
            }
            WSAPOLLFD descriptor{socket.value, static_cast<short>((can_receive ? POLLRDNORM : 0) | (!pending.empty() ? POLLWRNORM : 0)), 0};
            if (!descriptor.events) { std::this_thread::sleep_for(std::chrono::milliseconds(20)); continue; }
            // Keep queued writes responsive while the socket is waiting for inbound data.
            int polled = WSAPoll(&descriptor, 1, 5);
            if (polled == SOCKET_ERROR) fail("io", WSAGetLastError());
            if (polled > 0 && can_receive && (descriptor.revents & (POLLRDNORM | POLLHUP | POLLERR))) {
                char buffer[16384];
                int got = recv(socket.value, buffer, static_cast<int>(std::min(available, sizeof(buffer))), 0);
                if (!got) {
                    if (tls) fail("tls");
                    state = Closed; return;
                }
                if (got == SOCKET_ERROR) {
                    if (WSAGetLastError() != WSAEWOULDBLOCK) fail("io", WSAGetLastError());
                } else if (tls) {
                    if (cipher.size() + got > MiB) fail("limit");
                    cipher.insert(cipher.end(), buffer, buffer + got);
                } else {
                    std::lock_guard<std::mutex> lock(mutex);
                    received.append(buffer, got);
                }
            }
        }
    }
};

DWORD ruby_owner = 0;
VALUE error_class = Qnil, http_handle_class = Qnil, tcp_handle_class = Qnil;
struct Box { std::shared_ptr<Job> job; };
void free_box(void* pointer) {
    auto* box = static_cast<Box*>(pointer);
    box->job->cancel();
    delete box;
}
size_t box_size(const void*) { return sizeof(Box); }
const rb_data_type_t box_type = {"Lunetile network handle", {nullptr, free_box, box_size}, nullptr, nullptr, RUBY_TYPED_FREE_IMMEDIATELY};
void on_owner() { if (GetCurrentThreadId() != ruby_owner) rb_raise(rb_eThreadError, "Network API must run on the game thread"); }
Box* get_box(VALUE self) { on_owner(); Box* box; TypedData_Get_Struct(self, Box, &box_type, box); return box; }
VALUE make_error(const char* code, unsigned long native) {
    VALUE arguments[2]{ID2SYM(rb_intern(code)), ULONG2NUM(native)};
    return rb_class_new_instance(2, arguments, error_class);
}
// Ruby allocations can longjmp: protect them, then destroy native owners before rethrowing.
template<class Work> VALUE guarded(Work work) {
    int ruby_state = 0;
    bool memory_error = false;
    Failure error{nullptr};
    VALUE result = Qnil;
    {
        try { result = work(&ruby_state); }
        catch (Failure caught) { error = caught; }
        catch (const std::bad_alloc&) { memory_error = true; }
        catch (...) { error = {"io", 0}; }
    }
    if (ruby_state) rb_jump_tag(ruby_state);
    if (memory_error) rb_memerror();
    if (error.code) {
        if (!strcmp(error.code, "argument")) rb_raise(rb_eArgError, "Invalid network argument");
        rb_exc_raise(make_error(error.code, error.native));
    }
    return result;
}
struct Wrapped { Box* box; VALUE klass; };
VALUE pack_handle(VALUE pointer) {
    auto* wrapped = reinterpret_cast<Wrapped*>(pointer);
    return TypedData_Wrap_Struct(wrapped->klass, &box_type, wrapped->box);
}
VALUE wrap_job(const std::shared_ptr<Job>& job, VALUE klass, int* ruby_state) {
    auto box = std::make_unique<Box>(); box->job = job;
    launch(job);
    Wrapped wrapped{box.get(), klass};
    VALUE result = rb_protect(pack_handle, reinterpret_cast<VALUE>(&wrapped), ruby_state);
    if (!*ruby_state) box.release();
    else job->cancel();
    return result;
}
int timeout_value(VALUE value) {
    if (!RB_INTEGER_TYPE_P(value)) rb_raise(rb_eArgError, "timeout_ms must be an integer between 1 and 120000");
    int timeout = NUM2INT(value);
    if (timeout < 1 || timeout > 120000) rb_raise(rb_eArgError, "timeout_ms must be between 1 and 120000");
    return timeout;
}
VALUE http_start(VALUE, VALUE method, VALUE url, VALUE headers, VALUE body, VALUE milliseconds) {
    on_owner();
    if (finalizing) rb_exc_raise(make_error("closed", 0));
    Check_Type(method, T_STRING); Check_Type(url, T_STRING); Check_Type(headers, T_STRING); Check_Type(body, T_STRING);
    int timeout = timeout_value(milliseconds);
    return guarded([&](int* ruby_state) {
        auto job = std::make_shared<HttpJob>(std::string(RSTRING_PTR(method), RSTRING_LEN(method)), std::string(RSTRING_PTR(url), RSTRING_LEN(url)),
            std::string(RSTRING_PTR(headers), RSTRING_LEN(headers)), std::string(RSTRING_PTR(body), RSTRING_LEN(body)), timeout);
        return wrap_job(job, http_handle_class, ruby_state);
    });
}
VALUE tcp_connect(VALUE, VALUE host, VALUE port, VALUE tls, VALUE milliseconds) {
    on_owner(); Check_Type(host, T_STRING);
    if (finalizing) rb_exc_raise(make_error("closed", 0));
    int service = NUM2INT(port), timeout = timeout_value(milliseconds);
    if (service < 1 || service > 65535 || !RSTRING_LEN(host) || RSTRING_LEN(host) > 1024 ||
        (tls != Qtrue && tls != Qfalse) || memchr(RSTRING_PTR(host), 0, RSTRING_LEN(host))) rb_raise(rb_eArgError, "Invalid TCP address");
    return guarded([&](int* ruby_state) {
        start_winsock();
        auto job = std::make_shared<TcpJob>(std::string(RSTRING_PTR(host), RSTRING_LEN(host)), service, RTEST(tls), timeout);
        return wrap_job(job, tcp_handle_class, ruby_state);
    });
}
VALUE handle_state(VALUE self) {
    Box* box = get_box(self);
    return guarded([&](int*) { reap(); return ID2SYM(state_ids[box->job->state.load()]); });
}
VALUE handle_error(VALUE self) {
    Box* box = get_box(self);
    const char* code;
    unsigned long native;
    { std::lock_guard<std::mutex> lock(box->job->mutex); code = box->job->error; native = box->job->native_error; }
    return code ? make_error(code, native) : Qnil;
}
VALUE handle_cancel(VALUE self) { return get_box(self)->job->cancel() ? Qtrue : Qfalse; }
struct HttpResult { DWORD status; std::string headers, body; };
VALUE pack_http(VALUE pointer) {
    auto* result = reinterpret_cast<HttpResult*>(pointer);
    VALUE status = ULONG2NUM(result->status);
    VALUE headers = rb_utf8_str_new(result->headers.data(), static_cast<long>(result->headers.size()));
    VALUE body = rb_str_new(result->body.data(), static_cast<long>(result->body.size()));
    VALUE packed = rb_ary_new_from_args(3, status, headers, body);
    RB_GC_GUARD(headers); RB_GC_GUARD(body);
    return packed;
}
VALUE http_result(VALUE self) {
    auto* job = static_cast<HttpJob*>(get_box(self)->job.get());
    return guarded([&](int* ruby_state) {
        HttpResult result;
        {
            std::lock_guard<std::mutex> lock(job->mutex);
            if (job->state != Succeeded) return Qnil;
            result = {job->status, job->response_headers, job->response_body};
        }
        return rb_protect(pack_http, reinterpret_cast<VALUE>(&result), ruby_state);
    });
}
VALUE tcp_write(VALUE self, VALUE bytes) {
    auto* job = static_cast<TcpJob*>(get_box(self)->job.get());
    Check_Type(bytes, T_STRING);
    size_t count = RSTRING_LEN(bytes);
    return guarded([&](int*) {
        if (count > MiB) fail("backpressure");
        std::string copied(RSTRING_PTR(bytes), count);
        {
            std::lock_guard<std::mutex> lock(job->mutex);
            if (job->state != Open) fail("closed");
            if (count > MiB - job->queued) fail("backpressure");
            if (count) {
                job->writes.push_back({std::move(copied), 0, Clock::now() + std::chrono::milliseconds(job->timeout)});
                job->queued += count;
            }
        }
        return LONG2FIX(static_cast<long>(count));
    });
}
VALUE pack_bytes(VALUE pointer) {
    auto* bytes = reinterpret_cast<std::string*>(pointer);
    return rb_str_new(bytes->data(), static_cast<long>(bytes->size()));
}
VALUE tcp_read(int argc, VALUE* argv, VALUE self) {
    auto* job = static_cast<TcpJob*>(get_box(self)->job.get());
    VALUE maximum = Qnil; rb_scan_args(argc, argv, "01", &maximum);
    long count = NIL_P(maximum) ? 65536 : NUM2LONG(maximum);
    if (count < 1 || count > MiB) rb_raise(rb_eArgError, "read size must be between 1 and 1048576");
    return guarded([&](int* ruby_state) {
        std::string bytes;
        { std::lock_guard<std::mutex> lock(job->mutex); bytes = job->received.substr(0, count); }
        if (bytes.empty()) return Qnil;
        VALUE result = rb_protect(pack_bytes, reinterpret_cast<VALUE>(&bytes), ruby_state);
        if (!*ruby_state) { std::lock_guard<std::mutex> lock(job->mutex); job->received.erase(0, bytes.size()); }
        return result;
    });
}
VALUE network_counts(VALUE) {
    on_owner();
    return guarded([&](int* ruby_state) {
        reap();
        std::string counts(2, 0);
        for (const auto& job : jobs) ++counts[job->http ? 0 : 1];
        return rb_protect(pack_bytes, reinterpret_cast<VALUE>(&counts), ruby_state);
    });
}
}

void network_shutdown(bool final) {
    if (final) finalizing = true;
    for (const auto& job : jobs) job->cancel();
    for (const auto& job : jobs) if (job->worker.joinable()) job->worker.join();
    jobs.clear();
    if (winsock_started) { WSACleanup(); winsock_started = false; }
}
void init_network() {
    ruby_owner = GetCurrentThreadId();
    for (int i = 0; i < 7; ++i) state_ids[i] = rb_intern(state_names[i]);
    VALUE module = rb_define_module("Lunetile");
    error_class = rb_define_class_under(module, "NetworkError", rb_eStandardError);
    VALUE http = rb_define_module_under(module, "HTTP");
    VALUE tcp = rb_define_module_under(module, "TCP");
    http_handle_class = rb_define_class_under(http, "Handle", rb_cObject);
    tcp_handle_class = rb_define_class_under(tcp, "Connection", rb_cObject);
    rb_global_variable(&error_class); rb_global_variable(&http_handle_class); rb_global_variable(&tcp_handle_class);
    rb_undef_alloc_func(http_handle_class); rb_undef_alloc_func(tcp_handle_class);
    for (VALUE klass : {http_handle_class, tcp_handle_class}) {
        rb_define_method(klass, "state", RUBY_METHOD_FUNC(handle_state), 0);
        rb_define_method(klass, "error", RUBY_METHOD_FUNC(handle_error), 0);
    }
    rb_define_method(http_handle_class, "cancel", RUBY_METHOD_FUNC(handle_cancel), 0);
    rb_define_method(http_handle_class, "result", RUBY_METHOD_FUNC(http_result), 0);
    rb_define_method(tcp_handle_class, "close", RUBY_METHOD_FUNC(handle_cancel), 0);
    rb_define_method(tcp_handle_class, "read", RUBY_METHOD_FUNC(tcp_read), -1);
    rb_define_method(tcp_handle_class, "write", RUBY_METHOD_FUNC(tcp_write), 1);
    rb_define_singleton_method(http, "__start", RUBY_METHOD_FUNC(http_start), 5);
    rb_define_singleton_method(tcp, "__connect", RUBY_METHOD_FUNC(tcp_connect), 4);
    rb_define_singleton_method(module, "__network_counts", RUBY_METHOD_FUNC(network_counts), 0);
}
