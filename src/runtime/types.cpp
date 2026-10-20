#include <algorithm>
#include <cstdint>
#include <cstring>
#include <limits>
#include <ruby.h>
#include "table_data.h"

namespace {
#ifdef RGSS_VXA
uint64_t next_table_identity=0;
void table_changed(TableData* table,int x=-1,int y=-1,int z=-1) {
    ++table->revision;
    table->history[table->revision%64]={table->revision,x,y,z,x<0};
}
#endif
void table_free(void* pointer) {
    auto* table = static_cast<TableData*>(pointer);
    ruby_xfree(table->cells);
    ruby_xfree(table);
}
size_t table_size(const void* pointer) {
    return sizeof(TableData) + static_cast<const TableData*>(pointer)->count * sizeof(int16_t);
}
const rb_data_type_t table_type = {"RGSSXP::Table", {nullptr, table_free, table_size}, nullptr, nullptr, RUBY_TYPED_FREE_IMMEDIATELY};
TableData* get_table(VALUE object) {
    TableData* table;
    TypedData_Get_Struct(object, TableData, &table_type, table);
    return table;
}
VALUE table_alloc(VALUE klass) {
    auto* data=static_cast<TableData*>(ruby_xcalloc(1, sizeof(TableData)));
#ifdef RGSS_VXA
    data->identity=++next_table_identity;
#endif
    return TypedData_Wrap_Struct(klass, &table_type, data);
}
size_t count_cells(int x, int y, int z) {
    if (x < 0 || y < 0 || z < 0) rb_raise(rb_eArgError, "Negative Table dimension");
    // Validate before multiplication/allocation on x86, including untrusted Marshal input.
    constexpr size_t limit = 128 * 1024 * 1024 / sizeof(int16_t);
    size_t count = static_cast<size_t>(x);
    if (y && count > limit / y) rb_raise(rb_eArgError, "Table exceeds 128 MiB");
    count *= y;
    if (z && count > limit / z) rb_raise(rb_eArgError, "Table exceeds 128 MiB");
    count *= z;
    return count;
}
VALUE table_resize(int argc, VALUE* argv, VALUE self) {
    rb_check_arity(argc, 1, 3);
    rb_check_frozen(self);
    int x = NUM2INT(argv[0]), y = argc > 1 ? NUM2INT(argv[1]) : 1, z = argc > 2 ? NUM2INT(argv[2]) : 1;
    size_t count = count_cells(x, y, z);
    auto* table = get_table(self);
    auto* cells = static_cast<int16_t*>(ruby_xcalloc(count ? count : 1, sizeof(int16_t)));
    for (int k = 0; k < std::min(z, table->z); ++k)
        for (int j = 0; j < std::min(y, table->y); ++j)
            memcpy(cells + (static_cast<size_t>(k) * y + j) * x,
                   table->cells + (static_cast<size_t>(k) * table->y + j) * table->x,
                   std::min(x, table->x) * sizeof(int16_t));
    ruby_xfree(table->cells);
    table->dimensions=argc;table->x=x;table->y=y;table->z=z;table->count=count;table->cells=cells;
#ifdef RGSS_VXA
    table_changed(table);
#endif
    return self;
}
VALUE table_copy(VALUE self, VALUE other) {
    if (self == other) return self;
    rb_check_frozen(self);
    auto* source = get_table(other);
    auto* target = get_table(self);
    auto* cells = static_cast<int16_t*>(ruby_xcalloc(source->count ? source->count : 1, sizeof(int16_t)));
    memcpy(cells, source->cells, source->count * sizeof(int16_t));
    ruby_xfree(target->cells);
    target->dimensions=source->dimensions;target->x=source->x;target->y=source->y;target->z=source->z;target->count=source->count;
    target->cells = cells;
#ifdef RGSS_VXA
    table_changed(target);
#endif
    return self;
}
bool cell_offset(TableData* table, int argc, VALUE* argv, size_t& index) {
    rb_check_arity(argc, table->dimensions, table->dimensions);
    int x = NUM2INT(argv[0]), y = argc > 1 ? NUM2INT(argv[1]) : 0, z = argc > 2 ? NUM2INT(argv[2]) : 0;
    if (x < 0 || y < 0 || z < 0 || x >= table->x || y >= table->y || z >= table->z) return false;
    index = (static_cast<size_t>(z) * table->y + y) * table->x + x;
    return true;
}
VALUE table_get(int argc, VALUE* argv, VALUE self) {
    auto* table = get_table(self);
    size_t index;
    return cell_offset(table, argc, argv, index) ? INT2NUM(table->cells[index]) : Qnil;
}
VALUE table_set(int argc, VALUE* argv, VALUE self) {
    rb_check_arity(argc, 2, 4);
    rb_check_frozen(self);
    auto* table = get_table(self);
    size_t index;
    if (!cell_offset(table, argc - 1, argv, index)) return Qnil;
    int value = NUM2INT(argv[argc - 1]);
#ifdef RGSS_VXA
    if(table->cells[index]!=static_cast<int16_t>(static_cast<uint16_t>(value))) {
        int x=static_cast<int>(index%table->x),y=static_cast<int>(index/table->x%table->y),z=static_cast<int>(index/(static_cast<size_t>(table->x)*table->y));
        table_changed(table,x,y,z);
    }
#endif
    table->cells[index] = static_cast<int16_t>(static_cast<uint16_t>(value));
    return argv[argc - 1];
}
VALUE table_x(VALUE self) { return INT2NUM(get_table(self)->x); }
VALUE table_y(VALUE self) { return INT2NUM(get_table(self)->y); }
VALUE table_z(VALUE self) { return INT2NUM(get_table(self)->z); }
VALUE table_dump(VALUE self, VALUE) {
    auto* table = get_table(self);
    VALUE bytes = rb_str_new(nullptr, static_cast<long>(20 + table->count * 2));
    uint32_t header[] = {static_cast<uint32_t>(table->dimensions), static_cast<uint32_t>(table->x),
        static_cast<uint32_t>(table->y), static_cast<uint32_t>(table->z), static_cast<uint32_t>(table->count)};
    memcpy(RSTRING_PTR(bytes), header, sizeof(header));
    memcpy(RSTRING_PTR(bytes) + 20, table->cells, table->count * 2);
    return bytes;
}
VALUE table_load(VALUE klass, VALUE bytes) {
    StringValue(bytes);
    if (RSTRING_LEN(bytes) < 20) rb_raise(rb_eArgError, "Truncated Table header");
    uint32_t header[5];
    memcpy(header, RSTRING_PTR(bytes), sizeof(header));
    if (header[0] < 1 || header[0] > 3 || header[1] > INT_MAX || header[2] > INT_MAX || header[3] > INT_MAX)
        rb_raise(rb_eArgError, "Invalid Table shape");
    size_t count = count_cells(header[1], header[2], header[3]);
    if (header[4] != count || RSTRING_LEN(bytes) != 20 + count * 2 ||
        (header[0] == 1 && header[2] != 1) || (header[0] < 3 && header[3] != 1))
        rb_raise(rb_eArgError, "Table shape and payload disagree");
    VALUE result = table_alloc(klass);
    auto* table = get_table(result);
    table->cells = static_cast<int16_t*>(ruby_xcalloc(count ? count : 1, sizeof(int16_t)));
    table->dimensions = header[0]; table->x = header[1]; table->y = header[2]; table->z = header[3]; table->count = count;
    memcpy(table->cells, RSTRING_PTR(bytes) + 20, count * 2);
    return result;
}
}

#ifdef RGSS_VXA
const TableData* vxa_table_view(VALUE object) {
    return rb_typeddata_is_kind_of(object,&table_type)?get_table(object):nullptr;
}
#endif
void init_rgss_types() {
    VALUE table = rb_define_class("Table", rb_cObject);
    rb_define_alloc_func(table, table_alloc);
    rb_define_method(table, "initialize", RUBY_METHOD_FUNC(table_resize), -1);
    rb_define_method(table, "resize", RUBY_METHOD_FUNC(table_resize), -1);
    rb_define_method(table, "initialize_copy", RUBY_METHOD_FUNC(table_copy), 1);
    rb_define_method(table, "[]", RUBY_METHOD_FUNC(table_get), -1);
    rb_define_method(table, "[]=", RUBY_METHOD_FUNC(table_set), -1);
    rb_define_method(table, "xsize", RUBY_METHOD_FUNC(table_x), 0);
    rb_define_method(table, "ysize", RUBY_METHOD_FUNC(table_y), 0);
    rb_define_method(table, "zsize", RUBY_METHOD_FUNC(table_z), 0);
    rb_define_method(table, "_dump", RUBY_METHOD_FUNC(table_dump), 1);
    rb_define_singleton_method(table, "_load", RUBY_METHOD_FUNC(table_load), 1);
}
