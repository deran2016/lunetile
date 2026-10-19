#include <ruby.h>
void init_runtime_json(void);
static VALUE initialize_json(VALUE unused) { init_runtime_json(); return Qnil; }

/* The migration helper uses the same pinned x86 VM and encoding tables as the DLL. */
int main(int argc, char **argv) {
    ruby_sysinit(&argc, &argv);
    {
        RUBY_INIT_STACK;
        ruby_init();
        void *node = ruby_options(argc, argv);
        int status = 0;
        if (ruby_executable_node(node, &status)) {
            rb_protect(initialize_json, Qnil, &status);
            if (status) return ruby_cleanup(status);
        }
        return ruby_run_node(node);
    }
}
