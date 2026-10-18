"""Apply the reviewed MSVC 32-bit atomic fix to a separate Ruby 4.0.7 tree."""
import hashlib
import json
from pathlib import Path
import sys

ORIGINAL = '8d107d5c73034f22b8f231582b281ecef887793d720a5ca98689fce93230d861'
BEFORE = b'''#elif defined(_WIN32)
    return InterlockedExchangeAdd64(ptr, val);'''
AFTER = b'''#elif defined(_WIN64)
    return InterlockedExchangeAdd64(ptr, val);

#elif defined(_WIN32)
    RBIMPL_STATIC_ASSERT(size_of_size_t, sizeof *ptr == sizeof(rb_atomic_t));
    return rbimpl_atomic_fetch_add((volatile rb_atomic_t *)ptr, (rb_atomic_t)val, memory_order);'''

def patch(source):
    header = Path(source) / 'include/ruby/atomic.h'
    data = header.read_bytes()
    changed = data.replace(BEFORE, AFTER)
    expected = json.loads((Path(__file__).resolve().parents[1]/'src/runtime/ruby.lock.json').read_text())
    digest = hashlib.sha256(data).hexdigest()
    if digest == expected['patches'][0]['patched_sha256']:
        return digest
    if digest != ORIGINAL or data.count(BEFORE) != 1:
        raise ValueError('Unknown atomic.h; refusing to patch')
    result = hashlib.sha256(changed).hexdigest()
    if result != expected['patches'][0]['patched_sha256']:
        raise ValueError('Patched source hash mismatch')
    header.write_bytes(changed)
    return result

if __name__ == '__main__':
    print(patch(sys.argv[1]))
