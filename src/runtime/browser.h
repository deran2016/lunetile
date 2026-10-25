#pragma once
#include <windows.h>
void init_browser();
void browser_attach(HWND window);
void browser_reset();
void browser_shutdown();
void browser_layout();
void browser_pump();
bool browser_pretranslate(const MSG& message);
bool browser_input_blocked();
