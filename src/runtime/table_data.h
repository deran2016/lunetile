#pragma once
#include <cstdint>
#include <cstddef>
#include <ruby.h>

struct TableData {
    int dimensions, x, y, z;
    size_t count;
    int16_t* cells;
#ifdef RGSS_VXA
    struct Change { uint64_t revision; int x,y,z; bool all; };
    uint64_t identity, revision;
    Change history[64];
#endif
};
#ifdef RGSS_VXA
const TableData* vxa_table_view(VALUE object);
#endif
