/* Keep nmake child shell operations inside their build tree on every drive. */
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
int wmain(void) {
    wchar_t directory[32768], command[32768], system[32768];
    const wchar_t *tail = GetCommandLineW();
    STARTUPINFOW startup = {sizeof(startup)};
    PROCESS_INFORMATION process = {0};
    DWORD result;
    if (*tail == L'"') { ++tail; while (*tail && *tail != L'"') ++tail; if (*tail) ++tail; }
    else { while (*tail && *tail != L' ' && *tail != L'\t') ++tail; }
    if (!GetModuleFileNameW(NULL, directory, 32768) || !GetSystemDirectoryW(system, 32768)) return 2;
    *wcsrchr(directory, L'\\') = L'\0';
    if (wcscat_s(system, 32768, L"\\cmd.exe") ||
        swprintf_s(command, 32768, L"\"%ls\" %ls", system, tail) < 0) return 3;
    if (!CreateProcessW(system, command, NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL,
                        directory, &startup, &process)) {
        fwprintf(stderr,L"build shell CreateProcess: %lu\n",GetLastError()); return 4;
    }
    WaitForSingleObject(process.hProcess, INFINITE);
    if (!GetExitCodeProcess(process.hProcess, &result)) result = 5;
    CloseHandle(process.hThread); CloseHandle(process.hProcess);
    return (int)result;
}
