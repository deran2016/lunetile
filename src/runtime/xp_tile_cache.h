#pragma once
#include <ruby.h>
#include <cstddef>
struct Canvas;
void init_xp_tile_cache();
size_t xp_batch_count(VALUE command,size_t* flashes=nullptr);
using XPTileEmit=void(*)(void*,Canvas*,double,double,int,int,int,int,int,int);
void xp_batch_expand(VALUE command,void* target,XPTileEmit emit);
