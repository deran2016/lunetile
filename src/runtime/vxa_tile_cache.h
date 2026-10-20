#pragma once
#include <ruby.h>
#include <cstddef>
struct Canvas;
void init_vxa_tile_cache();
size_t vxa_batch_count(VALUE command);
using TileEmit=void(*)(void*,Canvas*,double,double,int,int,int,int);
void vxa_batch_expand(VALUE command,void* target,TileEmit emit);
