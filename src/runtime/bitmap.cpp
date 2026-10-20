#include <windows.h>
#include <wincodec.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <future>
#include <string>
#include <vector>
#include <wrl/client.h>
#include <ruby.h>
#include <ruby/encoding.h>
#include "graphics.h"

namespace {
VALUE bitmap_class, graphics_error;
void free_canvas(void* pointer) {
    auto* canvas = static_cast<Canvas*>(pointer);
    if (canvas->view) canvas->view->Release();
    if (canvas->texture) canvas->texture->Release();
    if (canvas->pixels) rb_gc_adjust_memory_usage(-static_cast<ssize_t>(static_cast<size_t>(canvas->width)*canvas->height*4));
    free(canvas->pixels);
    ruby_xfree(canvas);
}
size_t canvas_size(const void* pointer) {
    const auto* canvas = static_cast<const Canvas*>(pointer);
    return sizeof(Canvas) + (canvas->pixels ? static_cast<size_t>(canvas->width) * canvas->height * 4 : 0);
}
const rb_data_type_t canvas_type = {"RGSSXP::Bitmap", {nullptr, free_canvas, canvas_size}, nullptr, nullptr, RUBY_TYPED_FREE_IMMEDIATELY};
VALUE canvas_alloc(VALUE klass) { return TypedData_Wrap_Struct(klass, &canvas_type, ruby_xcalloc(1, sizeof(Canvas))); }
Canvas* raw_canvas(VALUE self) {
    Canvas* canvas;
    TypedData_Get_Struct(self, Canvas, &canvas_type, canvas);
    return canvas;
}
void dimensions(int width, int height) {
    if (width < 1 || height < 1 || width > 16384 || height > 16384 || static_cast<uint64_t>(width) * height * 4 > 128 * 1024 * 1024)
        rb_raise(rb_eArgError, "Bitmap shape exceeds supported 128 MiB / 16384 pixel limits");
}
VALUE canvas_empty(VALUE self, VALUE w, VALUE h) {
    int width = NUM2INT(w), height = NUM2INT(h);
    dimensions(width, height);
    auto* canvas = raw_canvas(self);
    if (canvas->pixels || canvas->disposed) rb_raise(graphics_error, "Bitmap is already initialized");
    auto* pixels = static_cast<unsigned char*>(calloc(static_cast<size_t>(width) * height, 4));
    if (!pixels) rb_memerror();
    canvas->width = width; canvas->height = height; canvas->pixels = pixels;
    rb_gc_adjust_memory_usage(static_cast<ssize_t>(static_cast<size_t>(width)*height*4));
    canvas_changed(canvas, 0, 0, width, height);
    return self;
}
struct Image { unsigned char* pixels = nullptr; UINT width = 0, height = 0; HRESULT result = E_FAIL; };
Image decode(std::vector<unsigned char> bytes) {
    using Microsoft::WRL::ComPtr;
    Image image;
    HRESULT initialized = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (FAILED(initialized)) { image.result = initialized; return image; }
    {
        ComPtr<IWICImagingFactory> factory;
        ComPtr<IWICStream> stream;
        ComPtr<IWICBitmapDecoder> decoder;
        ComPtr<IWICBitmapFrameDecode> frame;
        ComPtr<IWICFormatConverter> converter;
        HRESULT hr = CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&factory));
        if (SUCCEEDED(hr)) hr = factory->CreateStream(&stream);
        if (SUCCEEDED(hr)) hr = stream->InitializeFromMemory(bytes.data(), static_cast<DWORD>(bytes.size()));
        if (SUCCEEDED(hr)) hr = factory->CreateDecoderFromStream(stream.Get(), nullptr, WICDecodeMetadataCacheOnLoad, &decoder);
        if (SUCCEEDED(hr)) hr = decoder->GetFrame(0, &frame);
        if (SUCCEEDED(hr)) hr = frame->GetSize(&image.width, &image.height);
        uint64_t size = static_cast<uint64_t>(image.width) * image.height * 4;
        if (SUCCEEDED(hr) && (!image.width || !image.height || image.width > 16384 || image.height > 16384 || size > 128 * 1024 * 1024)) hr = E_INVALIDARG;
        if (SUCCEEDED(hr)) hr = factory->CreateFormatConverter(&converter);
        if (SUCCEEDED(hr)) hr = converter->Initialize(frame.Get(), GUID_WICPixelFormat32bppRGBA, WICBitmapDitherTypeNone, nullptr, 0, WICBitmapPaletteTypeCustom);
        if (SUCCEEDED(hr)) {
            image.pixels = static_cast<unsigned char*>(malloc(static_cast<size_t>(size)));
            if (!image.pixels) hr = E_OUTOFMEMORY;
        }
        if (SUCCEEDED(hr)) hr = converter->CopyPixels(nullptr, image.width * 4, static_cast<UINT>(size), image.pixels);
        image.result = hr;
        if (FAILED(hr)) { free(image.pixels); image.pixels = nullptr; }
    }
    CoUninitialize();
    return image;
}
VALUE canvas_decode(VALUE self, VALUE bytes) {
    StringValue(bytes);
    if (RSTRING_LEN(bytes) > 128 * 1024 * 1024) rb_raise(rb_eArgError, "Encoded image exceeds 128 MiB");
    auto* canvas = raw_canvas(self);
    if (canvas->pixels || canvas->disposed) rb_raise(graphics_error, "Bitmap is already initialized");
    Image image;
    char error[256]{};
    {
        try {
            std::vector<unsigned char> copied(RSTRING_PTR(bytes), RSTRING_PTR(bytes) + RSTRING_LEN(bytes));
            image = std::async(std::launch::async, decode, std::move(copied)).get();
        } catch (const std::exception& e) { strncpy_s(error, e.what(), _TRUNCATE); }
    }
    RB_GC_GUARD(bytes);
    if (*error) rb_raise(graphics_error, "Image worker: %s", error);
    if (FAILED(image.result)) rb_raise(graphics_error, "Image decode failed (HRESULT 0x%08lx)", image.result);
    canvas->pixels = image.pixels; canvas->width = image.width; canvas->height = image.height;
    rb_gc_adjust_memory_usage(static_cast<ssize_t>(static_cast<size_t>(canvas->width)*canvas->height*4));
    canvas_changed(canvas, 0, 0, canvas->width, canvas->height);
    return self;
}
VALUE canvas_dispose(VALUE self) {
    auto* canvas = raw_canvas(self);
    if (canvas->pixels) rb_gc_adjust_memory_usage(-static_cast<ssize_t>(static_cast<size_t>(canvas->width)*canvas->height*4));
    free(canvas->pixels); canvas->pixels = nullptr;
    if (canvas->view) { canvas->view->Release(); canvas->view = nullptr; }
    if (canvas->texture) { canvas->texture->Release(); canvas->texture = nullptr; }
    canvas->disposed = true;
    return Qnil;
}
VALUE canvas_disposed(VALUE self) { return raw_canvas(self)->disposed ? Qtrue : Qfalse; }
VALUE canvas_width(VALUE self) { return INT2NUM(canvas_get(self)->width); }
VALUE canvas_height(VALUE self) { return INT2NUM(canvas_get(self)->height); }
int component(VALUE color, const char* field) {
    return std::clamp(static_cast<int>(NUM2DBL(rb_funcall(color, rb_intern(field), 0))), 0, 255);
}
void color_bytes(VALUE color, unsigned char* bytes) {
    if (!rb_obj_is_kind_of(color, rb_path2class("Color"))) rb_raise(rb_eTypeError, "Expected Color");
    bytes[0] = static_cast<unsigned char>(component(color, "red")); bytes[1] = static_cast<unsigned char>(component(color, "green"));
    bytes[2] = static_cast<unsigned char>(component(color, "blue")); bytes[3] = static_cast<unsigned char>(component(color, "alpha"));
}
VALUE canvas_get_pixel(VALUE self, VALUE vx, VALUE vy) {
    auto* canvas = canvas_get(self);
    int x = NUM2INT(vx), y = NUM2INT(vy);
    unsigned char zero[4]{};
    auto* bytes = x >= 0 && y >= 0 && x < canvas->width && y < canvas->height ? canvas->pixels + (static_cast<size_t>(y) * canvas->width + x) * 4 : zero;
    VALUE args[] = {INT2NUM(bytes[0]), INT2NUM(bytes[1]), INT2NUM(bytes[2]), INT2NUM(bytes[3])};
    return rb_class_new_instance(4, args, rb_path2class("Color"));
}
VALUE canvas_set_pixel(VALUE self, VALUE vx, VALUE vy, VALUE color) {
    auto* canvas = canvas_get(self);
    int x = NUM2INT(vx), y = NUM2INT(vy);
    unsigned char bytes[4]; color_bytes(color, bytes);
    if (x >= 0 && y >= 0 && x < canvas->width && y < canvas->height) {
        memcpy(canvas->pixels + (static_cast<size_t>(y) * canvas->width + x) * 4, bytes, 4);
        canvas_changed(canvas, x, y, x + 1, y + 1);
    }
    return Qnil;
}
VALUE canvas_fill(VALUE self, VALUE vx, VALUE vy, VALUE vw, VALUE vh, VALUE color) {
    auto* canvas = canvas_get(self);
    int64_t x = NUM2INT(vx), y = NUM2INT(vy), width = NUM2INT(vw), height = NUM2INT(vh);
    unsigned char pixel[4]; color_bytes(color, pixel);
    if (width <= 0 || height <= 0) return Qnil;
    int left = static_cast<int>(std::clamp<int64_t>(x, 0, canvas->width));
    int top = static_cast<int>(std::clamp<int64_t>(y, 0, canvas->height));
    int right = static_cast<int>(std::clamp<int64_t>(x + width, 0, canvas->width));
    int bottom = static_cast<int>(std::clamp<int64_t>(y + height, 0, canvas->height));
    for (int j = top; j < bottom; ++j)
        for (int i = left; i < right; ++i) memcpy(canvas->pixels + (static_cast<size_t>(j) * canvas->width + i) * 4, pixel, 4);
    canvas_changed(canvas, left, top, right, bottom);
    return Qnil;
}
void over(unsigned char* target, const unsigned char* source, int opacity) {
    int alpha = (source[3] * opacity + 127) / 255;
    if (!target[3]) { memcpy(target, source, 3); target[3] = static_cast<unsigned char>(alpha); return; }
    if (!alpha) return;
    int numerator = alpha * 255 + target[3] * (255 - alpha);
    int weight = alpha * 65025 / numerator + 1;
    for (int c = 0; c < 3; ++c) target[c] = static_cast<unsigned char>((source[c] * weight + target[c] * (256 - weight)) >> 8);
    target[3] = static_cast<unsigned char>(numerator / 255);
}
VALUE canvas_blt(VALUE self, VALUE spec) {
    Check_Type(spec, T_ARRAY);
    if (RARRAY_LEN(spec) != 10) rb_raise(rb_eArgError, "Invalid blt descriptor");
    auto* target = canvas_get(self);
    auto* source = canvas_get(rb_ary_entry(spec, 4));
    int x = NUM2INT(rb_ary_entry(spec, 0)), y = NUM2INT(rb_ary_entry(spec, 1));
    int w = NUM2INT(rb_ary_entry(spec, 2)), h = NUM2INT(rb_ary_entry(spec, 3));
    int sx = NUM2INT(rb_ary_entry(spec, 5)), sy = NUM2INT(rb_ary_entry(spec, 6));
    int sw = NUM2INT(rb_ary_entry(spec, 7)), sh = NUM2INT(rb_ary_entry(spec, 8));
    int opacity = std::clamp(NUM2INT(rb_ary_entry(spec, 9)), 0, 255);
    if (w <= 0 || h <= 0 || sw <= 0 || sh <= 0 || !opacity) return Qnil;
    unsigned char* snapshot = nullptr;
    if (target == source) {
        size_t size = static_cast<size_t>(source->width) * source->height * 4;
        snapshot = static_cast<unsigned char*>(malloc(size));
        if (!snapshot) rb_memerror();
        memcpy(snapshot, source->pixels, size);
    }
    const unsigned char* input = snapshot ? snapshot : source->pixels;
    int left = static_cast<int>(std::clamp<int64_t>(x, 0, target->width));
    int top = static_cast<int>(std::clamp<int64_t>(y, 0, target->height));
    int right = static_cast<int>(std::clamp<int64_t>(static_cast<int64_t>(x) + w, 0, target->width));
    int bottom = static_cast<int>(std::clamp<int64_t>(static_cast<int64_t>(y) + h, 0, target->height));
    for (int j = top; j < bottom; ++j) {
        int64_t v = sy + (static_cast<int64_t>(j) - y) * sh / h;
        if (v < 0 || v >= source->height) continue;
        for (int i = left; i < right; ++i) {
            int64_t u = sx + (static_cast<int64_t>(i) - x) * sw / w;
            if (u < 0 || u >= source->width) continue;
            over(target->pixels + (static_cast<size_t>(j) * target->width + i) * 4,
                 input + (static_cast<size_t>(v) * source->width + static_cast<size_t>(u)) * 4, opacity);
        }
    }
    free(snapshot);
    canvas_changed(target, left, top, right, bottom);
    return Qnil;
}
VALUE canvas_copy(VALUE self, VALUE other) {
    if (self == other) return self;
    auto* source = canvas_get(other);
    canvas_empty(self, INT2NUM(source->width), INT2NUM(source->height));
    auto* target = canvas_get(self);
    memcpy(target->pixels, source->pixels, static_cast<size_t>(source->width) * source->height * 4);
    return self;
}
// The RGSS1 font size is GDI's positive cell height, not a negative em height.
VALUE canvas_text(VALUE self, VALUE text, VALUE font, VALUE spec) {
    auto* canvas = canvas_get(self);
    Check_Type(text, T_STRING); Check_Type(spec, T_ARRAY);
    if (RARRAY_LEN(spec) != 6) rb_raise(rb_eArgError, "Invalid text descriptor");
    VALUE name = rb_funcall(font, rb_intern("name"), 0);
    StringValue(name);
    int size = NUM2INT(rb_funcall(font, rb_intern("size"), 0));
    bool bold = RTEST(rb_funcall(font, rb_intern("bold"), 0)), italic = RTEST(rb_funcall(font, rb_intern("italic"), 0));
    unsigned char color[4]; color_bytes(rb_funcall(font, rb_intern("color"), 0), color);
    int x = NUM2INT(rb_ary_entry(spec, 0)), y = NUM2INT(rb_ary_entry(spec, 1));
    int w = NUM2INT(rb_ary_entry(spec, 2)), h = NUM2INT(rb_ary_entry(spec, 3));
    int align = NUM2INT(rb_ary_entry(spec, 4)); bool measure = RTEST(rb_ary_entry(spec, 5));
    VALUE utf = rb_str_encode(text, rb_enc_from_encoding(rb_utf8_encoding()), 0, Qnil);
    int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, RSTRING_PTR(utf), static_cast<int>(RSTRING_LEN(utf)), nullptr, 0);
    if (RSTRING_LEN(utf) && !count) rb_raise(rb_eEncodingError, "Invalid UTF-8 text");
    VALUE wide_text = rb_str_new(nullptr, (count + 1) * sizeof(wchar_t));
    MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, RSTRING_PTR(utf), static_cast<int>(RSTRING_LEN(utf)), reinterpret_cast<wchar_t*>(RSTRING_PTR(wide_text)), count);
    reinterpret_cast<wchar_t*>(RSTRING_PTR(wide_text))[count] = 0;
    VALUE utf_name = rb_str_encode(name, rb_enc_from_encoding(rb_utf8_encoding()), 0, Qnil);
    wchar_t face[LF_FACESIZE]{};
    MultiByteToWideChar(CP_UTF8, 0, StringValueCStr(utf_name), -1, face, LF_FACESIZE);
    SIZE extent{};
    HDC dc = CreateCompatibleDC(nullptr);
    HFONT handle = CreateFontW(size, 0, 0, 0, bold ? FW_BOLD : FW_NORMAL, italic, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, ANTIALIASED_QUALITY, DEFAULT_PITCH, face);
    if (!dc || !handle) { if (dc) DeleteDC(dc); if (handle) DeleteObject(handle); rb_raise(graphics_error, "GDI font allocation failed"); }
    HGDIOBJ old_font = SelectObject(dc, handle);
    auto* characters = reinterpret_cast<const wchar_t*>(RSTRING_PTR(wide_text));
    GetTextExtentPoint32W(dc, characters, count, &extent);
    if (!count) extent = {};
    if (!measure && count && w > 0 && h > 0 && extent.cx > 0 && extent.cy > 0 && extent.cx <= 32768) {
        BITMAPINFO info{}; info.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
        info.bmiHeader.biWidth = extent.cx; info.bmiHeader.biHeight = -extent.cy;
        info.bmiHeader.biPlanes = 1; info.bmiHeader.biBitCount = 32; info.bmiHeader.biCompression = BI_RGB;
        void* bits = nullptr;
        HBITMAP mask = CreateDIBSection(dc, &info, DIB_RGB_COLORS, &bits, nullptr, 0);
        if (!mask || !bits) {
            if (mask) DeleteObject(mask);
            SelectObject(dc, old_font); DeleteObject(handle); DeleteDC(dc);
            rb_raise(graphics_error, "GDI text mask allocation failed");
        }
        if (mask) {
            HGDIOBJ old_bitmap = SelectObject(dc, mask);
            memset(bits, 0, static_cast<size_t>(extent.cx) * extent.cy * 4);
            SetTextColor(dc, RGB(255,255,255)); SetBkColor(dc, RGB(0,0,0)); SetBkMode(dc, OPAQUE);
            TextOutW(dc, 0, 0, characters, count);
            GdiFlush();
            int draw_width = std::min(w, static_cast<int>(extent.cx));
            int left = x + (align == 1 ? (w - draw_width) / 2 : align == 2 ? w - draw_width : 0);
            int top = y + (h - extent.cy) / 2;
            for (int j = 0; j < extent.cy; ++j) {
                int64_t dy = static_cast<int64_t>(top) + j;
                if (dy < 0 || dy >= canvas->height || dy < y || dy >= static_cast<int64_t>(y) + h) continue;
                for (int i = 0; i < draw_width; ++i) {
                    int64_t dx = static_cast<int64_t>(left) + i;
                    if (dx < 0 || dx >= canvas->width) continue;
                    int u = static_cast<int>(static_cast<int64_t>(i) * extent.cx / draw_width);
                    unsigned char pixel[] = {color[0],color[1],color[2],static_cast<unsigned char>(static_cast<unsigned char*>(bits)[(static_cast<size_t>(j)*extent.cx+u)*4] * color[3] / 255)};
                    over(canvas->pixels + (static_cast<size_t>(dy)*canvas->width+static_cast<size_t>(dx))*4, pixel, 255);
                }
            }
            SelectObject(dc, old_bitmap); DeleteObject(mask);
            canvas_changed(canvas, 0, 0, canvas->width, canvas->height);
        }
    }
    SelectObject(dc, old_font); DeleteObject(handle); DeleteDC(dc);
    RB_GC_GUARD(utf); RB_GC_GUARD(utf_name); RB_GC_GUARD(wide_text);
    return rb_ary_new_from_args(2, INT2NUM(extent.cx), INT2NUM(extent.cy));
}
VALUE canvas_hue(VALUE self, VALUE angle) {
    auto* canvas = canvas_get(self);
    double shift = std::fmod(NUM2DBL(angle), 360.0) / 60.0;
    for (size_t i = 0, count = static_cast<size_t>(canvas->width) * canvas->height; i < count; ++i) {
        auto* p = canvas->pixels + i * 4;
        double r=p[0]/255.0,g=p[1]/255.0,b=p[2]/255.0;
        double hi=std::max({r,g,b}),lo=std::min({r,g,b}),delta=hi-lo;
        if (!delta) continue;
        double hue=(hi==r?(g-b)/delta:hi==g?2+(b-r)/delta:4+(r-g)/delta)+shift;
        hue=std::fmod(hue+12,6.0); double saturation=delta/hi;
        double c=hi*saturation,second=c*(1-std::abs(std::fmod(hue,2.0)-1)),m=hi-c;
        double rgb[3]{};
        int sector=static_cast<int>(hue);
        if(sector==0){rgb[0]=c;rgb[1]=second;}else if(sector==1){rgb[0]=second;rgb[1]=c;}
        else if(sector==2){rgb[1]=c;rgb[2]=second;}else if(sector==3){rgb[1]=second;rgb[2]=c;}
        else if(sector==4){rgb[0]=second;rgb[2]=c;}else{rgb[0]=c;rgb[2]=second;}
        for(int j=0;j<3;++j)p[j]=static_cast<unsigned char>(std::clamp(static_cast<int>((rgb[j]+m)*255+0.5),0,255));
    }
    canvas_changed(canvas,0,0,canvas->width,canvas->height); return Qnil;
}
}

#ifdef RGSS_VXA
static int CALLBACK found_font(const LOGFONTW*,const TEXTMETRICW*,DWORD,LPARAM result) {
    *reinterpret_cast<bool*>(result)=true;return 0;
}
static VALUE font_exists(VALUE,VALUE name) {
    StringValue(name);
    VALUE utf=rb_str_encode(name,rb_enc_from_encoding(rb_utf8_encoding()),0,Qnil);
    LOGFONTW font{};font.lfCharSet=DEFAULT_CHARSET;
    int count=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,RSTRING_PTR(utf),static_cast<int>(RSTRING_LEN(utf)),font.lfFaceName,LF_FACESIZE-1);
    if(!count)return Qfalse;
    bool found=false;
    HDC dc=GetDC(nullptr);
    if(!dc)return Qfalse;
    EnumFontFamiliesExW(dc,&font,found_font,reinterpret_cast<LPARAM>(&found),0);
    ReleaseDC(nullptr,dc);
    return found?Qtrue:Qfalse;
}
static VALUE vxa_blur(VALUE object) {
    Canvas* canvas=canvas_get(object);
    const int w=canvas->width,h=canvas->height;
    VALUE buffer=rb_str_new(nullptr,static_cast<long>(w)*h*4);
    auto* out=reinterpret_cast<unsigned char*>(RSTRING_PTR(buffer));
    for(int y=0;y<h;++y)for(int x=0;x<w;++x)for(int c=0;c<4;++c){
        unsigned sum=0;
        for(int dy=-1;dy<=1;++dy)for(int dx=-1;dx<=1;++dx)
            sum+=canvas->pixels[(static_cast<size_t>(std::clamp(y+dy,0,h-1))*w+std::clamp(x+dx,0,w-1))*4+c];
        out[(static_cast<size_t>(y)*w+x)*4+c]=static_cast<unsigned char>((sum+4)/9);
    }
    memcpy(canvas->pixels,out,static_cast<size_t>(w)*h*4);
    canvas_changed(canvas,0,0,w,h);
    RB_GC_GUARD(buffer);
    return Qnil;
}
static VALUE vxa_radial_blur(VALUE object,VALUE angle_value,VALUE division_value) {
    const int angle=std::clamp(NUM2INT(angle_value),0,359);
    const int divisions=std::clamp(NUM2INT(division_value),2,100);
    Canvas* canvas=canvas_get(object);
    const int w=canvas->width,h=canvas->height;
    VALUE buffer=rb_str_new(nullptr,static_cast<long>(w)*h*4);
    auto* out=reinterpret_cast<unsigned char*>(RSTRING_PTR(buffer));
    const double cx=(w-1)*.5,cy=(h-1)*.5;
    double cosine[100]{},sine[100]{};
    for(int i=0;i<divisions;++i){
        double radians=(static_cast<double>(i)/(divisions-1)-.5)*angle*3.141592653589793/180;
        cosine[i]=cos(radians);sine[i]=sin(radians);
    }
    for(int y=0;y<h;++y)for(int x=0;x<w;++x){
        unsigned sum[4]{};
        for(int i=0;i<divisions;++i){
            int sx=static_cast<int>(std::round(cx+(x-cx)*cosine[i]-(y-cy)*sine[i]));
            int sy=static_cast<int>(std::round(cy+(x-cx)*sine[i]+(y-cy)*cosine[i]));
            if(sx<0||sy<0||sx>=w||sy>=h)continue;
            const auto* p=canvas->pixels+(static_cast<size_t>(sy)*w+sx)*4;
            for(int c=0;c<4;++c)sum[c]+=p[c];
        }
        for(int c=0;c<4;++c)out[(static_cast<size_t>(y)*w+x)*4+c]=static_cast<unsigned char>(sum[c]/divisions);
    }
    memcpy(canvas->pixels,out,static_cast<size_t>(w)*h*4);
    canvas_changed(canvas,0,0,w,h);
    RB_GC_GUARD(buffer);
    return Qnil;
}
#endif

Canvas* canvas_get(VALUE object) {
    auto* canvas = raw_canvas(object);
    if (canvas->disposed || !canvas->pixels) rb_raise(graphics_error, "disposed bitmap");
    return canvas;
}
void canvas_changed(Canvas* canvas, int left, int top, int right, int bottom) {
    if (left >= right || top >= bottom) return;
    RECT rect{left,top,right,bottom};
    if (!canvas->dirty) canvas->changed=rect;
    else UnionRect(&canvas->changed,&canvas->changed,&rect);
    canvas->dirty=true;
}
void init_bitmap() {
    graphics_error = rb_define_class("RGSSError",rb_eStandardError);
    bitmap_class = rb_define_class("Bitmap",rb_cObject);
    rb_global_variable(&graphics_error);
    rb_global_variable(&bitmap_class);
    rb_define_alloc_func(bitmap_class,canvas_alloc);
    rb_define_private_method(bitmap_class,"__empty",RUBY_METHOD_FUNC(canvas_empty),2);
    rb_define_private_method(bitmap_class,"__decode",RUBY_METHOD_FUNC(canvas_decode),1);
    rb_define_private_method(bitmap_class,"__fill",RUBY_METHOD_FUNC(canvas_fill),5);
    rb_define_private_method(bitmap_class,"__blt",RUBY_METHOD_FUNC(canvas_blt),1);
    rb_define_private_method(bitmap_class,"__text",RUBY_METHOD_FUNC(canvas_text),3);
    rb_define_private_method(bitmap_class,"__copy",RUBY_METHOD_FUNC(canvas_copy),1);
    rb_define_method(bitmap_class,"width",RUBY_METHOD_FUNC(canvas_width),0);
    rb_define_method(bitmap_class,"height",RUBY_METHOD_FUNC(canvas_height),0);
    rb_define_method(bitmap_class,"get_pixel",RUBY_METHOD_FUNC(canvas_get_pixel),2);
    rb_define_method(bitmap_class,"set_pixel",RUBY_METHOD_FUNC(canvas_set_pixel),3);
    rb_define_method(bitmap_class,"dispose",RUBY_METHOD_FUNC(canvas_dispose),0);
    rb_define_method(bitmap_class,"disposed?",RUBY_METHOD_FUNC(canvas_disposed),0);
    rb_define_method(bitmap_class,"hue_change",RUBY_METHOD_FUNC(canvas_hue),1);
#ifdef RGSS_VXA
    rb_define_method(bitmap_class,"__blur",RUBY_METHOD_FUNC(vxa_blur),0);
    rb_define_method(bitmap_class,"__radial_blur",RUBY_METHOD_FUNC(vxa_radial_blur),2);
    rb_define_singleton_method(rb_define_class("Font",rb_cObject),"exist?",RUBY_METHOD_FUNC(font_exists),1);
#endif
}
