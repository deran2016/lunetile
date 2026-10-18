#include <ruby.h>

/* The migration helper uses the same pinned x86 VM and encoding tables as the DLL. */
int main(int argc, char **argv) {
    ruby_sysinit(&argc, &argv);
    {
        RUBY_INIT_STACK;
        ruby_init();
        return ruby_run_node(ruby_options(argc, argv));
    }
}
