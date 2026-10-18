/* Detect a 64-bit atomic operation overwriting the next 32-bit size_t. */
#include <stdio.h>
#include <ruby.h>
#include <ruby/atomic.h>
int main(void) {
    __declspec(align(8)) volatile size_t slots[2];
    size_t previous;
    if (sizeof(size_t) != 4) return 2;
    slots[0] = (size_t)-1;
    slots[1] = 0x12345678;
    previous = rbimpl_atomic_size_fetch_add(&slots[0], 1, 0);
    printf("size_t=%u previous=%08lx value=%08lx neighbor=%08lx expected=12345678\n",
           (unsigned)sizeof(size_t), (unsigned long)previous,
           (unsigned long)slots[0], (unsigned long)slots[1]);
    if (previous != (size_t)-1 || slots[0] != 0 || slots[1] != 0x12345678) return 1;
    RUBY_ATOMIC_SIZE_SUB(slots[0], 1);
    if (slots[0] != (size_t)-1 || slots[1] != 0x12345678) return 3;
    RUBY_ATOMIC_SIZE_INC(slots[0]);
    RUBY_ATOMIC_SIZE_DEC(slots[0]);
    if (slots[0] != (size_t)-1 || slots[1] != 0x12345678) return 4;
    previous = RUBY_ATOMIC_SIZE_CAS(slots[0], (size_t)-1, 42);
    if (previous != (size_t)-1 || slots[0] != 42) return 5;
    previous = RUBY_ATOMIC_SIZE_CAS(slots[0], 99, 7);
    if (previous != 42 || slots[0] != 42) return 6;
    previous = RUBY_ATOMIC_SIZE_EXCHANGE(slots[0], (size_t)-1);
    if (previous != 42 || slots[1] != 0x12345678) return 7;
    RUBY_ATOMIC_SIZE_ADD(slots[0], 1);
    if (slots[0] != 0 || slots[1] != 0x12345678) return 8;
    puts("32-bit fetch/add/sub/inc/dec/exchange/CAS boundaries: PASS");
    return 0;
}
