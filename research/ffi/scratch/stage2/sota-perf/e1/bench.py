import sys, time, ctypes, os
sys.path.insert(0, sys.argv[1])
mods = sys.argv[2:]
N = 2_000_000
def best(fn, reps=5):
    b = 1e9
    for _ in range(reps):
        t = time.perf_counter(); fn(); b = min(b, time.perf_counter() - t)
    return b
def loop_empty():
    for i in range(N): pass
base = best(loop_empty)
def pyadd(a, b): return a + b
def loop_py():
    f = pyadd
    for i in range(N): f(i, 1)
lib = ctypes.CDLL(os.path.join(os.path.dirname(os.path.abspath(__file__)), "libcadd.so"))
lib.cadd.argtypes = [ctypes.c_int64, ctypes.c_int64]; lib.cadd.restype = ctypes.c_int64
def loop_ct():
    f = lib.cadd
    for i in range(N): f(i, 1)
print(f"{sys.version.split()[0]} gil={getattr(sys, '_is_gil_enabled', lambda: True)()} empty loop {base/N*1e9:.1f} ns/iter")
print(f"  python def add      {(best(loop_py)-base)/N*1e9:6.1f} ns/call")
print(f"  ctypes cadd         {(best(loop_ct)-base)/N*1e9:6.1f} ns/call")
for name in mods:
    m = __import__(name)
    def loop_noop(f=m.noop):
        for i in range(N): f()
    def loop_add(f=m.add):
        for i in range(N): f(i, 1)
    K = 1_000_000
    def cb(x): return x
    ck = best(lambda: m.callk(cb, K)); cva = best(lambda: m.callk_va(cb, K)); cpk = best(lambda: m.callk_park(cb, K))
    print(f"  {name:8s} {os.path.basename(m.__file__):40s} noop {(best(loop_noop)-base)/N*1e9:5.1f}  add {(best(loop_add)-base)/N*1e9:5.1f} ns/call | Pys->Py vectorcall {ck/K*1e9:5.1f}  +park {cpk/K*1e9:5.1f}  CallFunction(\"L\") {cva/K*1e9:5.1f} ns/call")
