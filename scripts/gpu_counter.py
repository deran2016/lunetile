"""PID-scoped GPU engine counters; no ETW session, elevation or settings changes.

Running Time is cumulative GPU-engine time, in 100 ns units. The raw
Utilization Percentage numerator (PERF_100NSEC_TIMER) is also retained to
cross-check that unit on the installed provider. Engine times may overlap:
their sum is engine work, NOT frame latency or GPU wall-clock duration.
New/reset instances establish a baseline; vanished instances lose their
unobserved tail. Only continuous instances contribute interval deltas.
"""
import ctypes as C
from ctypes import wintypes as W
import os
import time


class Raw(C.Structure):
    _fields_ = [('status', W.DWORD), ('timestamp', W.FILETIME),
                ('first', C.c_longlong), ('second', C.c_longlong),
                ('multi', W.DWORD)]


class Item(C.Structure):
    _fields_ = [('name', W.LPWSTR), ('raw', Raw)]


def intervals(previous, current):
    """Inputs map instance to (running ticks, wall ticks, utilization ticks)."""
    rows = []
    for name, (running, stamp, utilization) in current.items():
        old = previous.get(name)
        valid = old is not None and running >= old[0] and stamp > old[1]
        rows.append({'instance': name, 'running_100ns': running,
                     'timestamp_100ns': stamp, 'utilization_raw': utilization,
                     'unit_crosscheck': running == utilization,
                     'delta_ms': (running-old[0])/10000 if valid else None,
                     'interval_ms': (stamp-old[1])/10000 if valid else None,
                     'percent': 100*(running-old[0])/(stamp-old[1]) if valid else None,
                     'baseline_only': not valid})
    return rows


class GpuCounter:
    def __init__(self, pid):
        if not isinstance(pid, int) or pid <= 0:
            raise ValueError('pid must be a positive integer')
        self.pid = pid
        self.previous = {}
        self.dll = C.WinDLL('pdh.dll')
        signatures = {
            'PdhOpenQueryW': [W.LPCWSTR, C.c_size_t, C.POINTER(W.HANDLE)],
            'PdhAddEnglishCounterW': [W.HANDLE, W.LPCWSTR, C.c_size_t, C.POINTER(W.HANDLE)],
            'PdhCollectQueryData': [W.HANDLE],
            'PdhCloseQuery': [W.HANDLE],
            'PdhGetRawCounterArrayW': [W.HANDLE, C.POINTER(W.DWORD), C.POINTER(W.DWORD), C.c_void_p],
            'PdhGetCounterInfoW': [W.HANDLE, C.c_ubyte, C.POINTER(W.DWORD), C.c_void_p],
            'PdhGetCounterTimeBase': [W.HANDLE, C.POINTER(C.c_longlong)],
        }
        for name, args in signatures.items():
            fn = getattr(self.dll, name)
            fn.argtypes = args
            fn.restype = W.DWORD
        self.query = W.HANDLE()
        self._check(self.dll.PdhOpenQueryW(None, 0, C.byref(self.query)))
        self.counters = []
        self.metadata = []
        try:
            for name in ('Running Time', 'Utilization Percentage'):
                handle = W.HANDLE()
                path = f'\\GPU Engine(pid_{pid}_*)\\{name}'
                self._check(self.dll.PdhAddEnglishCounterW(self.query, path, 0, C.byref(handle)))
                self.counters.append(handle)
                size = W.DWORD()
                status = self.dll.PdhGetCounterInfoW(handle, False, C.byref(size), None)
                if status != 0x800007D2:
                    self._check(status)
                buf = C.create_string_buffer(size.value)
                self._check(self.dll.PdhGetCounterInfoW(handle, False, C.byref(size), buf))
                counter_type = W.DWORD.from_buffer(buf, 4).value
                base = C.c_longlong()
                status = self.dll.PdhGetCounterTimeBase(handle, C.byref(base))
                self.metadata.append({'counter':name,'type':counter_type,'time_base':base.value if not status else None,'time_base_status':status})
            if self.metadata[1]['type'] != 0x20510500 or self.metadata[1]['time_base'] != 10000000:
                raise RuntimeError('GPU utilization does not report a 100 ns timer/time base')
        except Exception:
            self.close()
            raise

    @staticmethod
    def _check(status):
        if status:
            raise OSError(f'PDH status 0x{status:08x}')

    def _read(self, handle):
        for _ in range(3):
            size, count = W.DWORD(), W.DWORD()
            status = self.dll.PdhGetRawCounterArrayW(handle, C.byref(size), C.byref(count), None)
            if status in (0x800007D5, 0x800007D1):  # no data / no instance
                return {}
            if status not in (0, 0x800007D2):
                self._check(status)
            if not size.value:
                return {}
            buf = C.create_string_buffer(size.value)
            status = self.dll.PdhGetRawCounterArrayW(handle, C.byref(size), C.byref(count), buf)
            if status == 0x800007D2:
                continue
            self._check(status)
            items = C.cast(buf, C.POINTER(Item))
            result = {}
            for i in range(count.value):
                item = items[i]
                if item.name.startswith(f'pid_{self.pid}_') and item.raw.status in (0, 1):
                    stamp = (item.raw.timestamp.dwHighDateTime << 32) | item.raw.timestamp.dwLowDateTime
                    result[item.name] = (item.raw.first, stamp)
            return result
        raise RuntimeError('GPU counter instances changed during three reads')

    def sample(self):
        started = time.perf_counter()
        status = self.dll.PdhCollectQueryData(self.query)
        if status == 0x800007D5:
            current = {}
        else:
            self._check(status)
            running, utilization = (self._read(h) for h in self.counters)
            current = {name: (value, stamp, utilization.get(name, (None,))[0])
                       for name, (value, stamp) in running.items()}
        rows = intervals(self.previous, current)
        disappeared = sorted(self.previous.keys() - current.keys())
        self.previous = current
        return {'pid': self.pid, 'engines': rows, 'disappeared': disappeared,
                'available': bool(current), 'metadata':self.metadata,
                'sample_cost_ms': (time.perf_counter()-started)*1000}

    def close(self):
        if self.query:
            self.dll.PdhCloseQuery(self.query)
            self.query = W.HANDLE()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == '__main__':
    import json
    old = {'same': (10000, 100000, 10000), 'reset': (100, 100000, 100)}
    new = {'same': (30000, 200000, 30000), 'reset': (50, 200000, 50), 'new': (9, 200000, 9)}
    rows = {r['instance']: r for r in intervals(old, new)}
    assert rows['same']['delta_ms'] == 2 and rows['same']['percent'] == 20
    assert rows['reset']['delta_ms'] is None and rows['new']['baseline_only']
    assert intervals(old, {}) == []
    with GpuCounter(os.getpid()) as gpu:
        print(json.dumps({'self_check': 'passed', 'own_process_probe': gpu.sample()}))
