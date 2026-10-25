#pragma once
#include <cstdint>
#include <cstddef>
#include <ruby.h>

struct TableData {
    int dimensions, x, y, z;
    size_t count;
    int16_t* cells;
    struct Change { uint64_t revision; int x,y,z; bool all; };
    uint64_t identity, revision;
#ifdef RGSS_VXA
    Change history[64];
#else
    Change* history;
#endif
};
TableData* native_table_view(VALUE object);
#ifdef RGSS_VXA
const TableData* vxa_table_view(VALUE object);
#else
void observe_table(TableData* table);
#endif
