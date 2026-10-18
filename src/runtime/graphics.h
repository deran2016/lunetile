#pragma once
#include <windows.h>
#include <d3d11.h>
#include <ruby.h>

struct Canvas {
    int width, height;
    unsigned char* pixels;
    bool disposed, dirty;
    RECT changed;
    ID3D11Texture2D* texture;
    ID3D11ShaderResourceView* view;
};
Canvas* canvas_get(VALUE object);
void canvas_changed(Canvas* canvas, int left, int top, int right, int bottom);
void init_bitmap();
void init_graphics();
void graphics_prepare();
void graphics_attach(HWND window);
void graphics_shutdown();
void graphics_reset();
void input_reset();
bool input_take_reset();
void init_input();
void input_attach(HWND window);
void input_message(UINT message, WPARAM keycode);
