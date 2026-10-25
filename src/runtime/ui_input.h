#pragma once
#include <windows.h>
void init_ui_input();
void ui_input_update();
void ui_input_pretranslate(const MSG& message);
void ui_input_reset();
bool ui_input_message(HWND window, UINT message, WPARAM wparam, LPARAM lparam);
void graphics_input_size(int& width, int& height);
