#include <ruby.h>
#include "json_builtin.h"
extern "C" void ruby_init_ext(const char*, void (*)(void));
extern "C" void Init_parser();
extern "C" void Init_generator();

extern "C" void init_runtime_json() {
    ruby_init_ext("json/version.so", init_json_version);
    ruby_init_ext("json/common.so", init_json_common);
    ruby_init_ext("json/ext/generator/state.so", init_json_state);
    ruby_init_ext("json/ext/parser.so", Init_parser);
    ruby_init_ext("json/ext/generator.so", Init_generator);
    ruby_init_ext("json/ext.so", init_json_ext);
    ruby_init_ext("json.so", init_json_root);
    rb_require("json");
}
