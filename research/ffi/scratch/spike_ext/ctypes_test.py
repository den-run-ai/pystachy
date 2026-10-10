import ctypes
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
lib = ctypes.CDLL(os.path.join(HERE, sys.argv[2] if len(sys.argv) > 2 else "libpysnaive.so"))
I = ctypes.c_int64
P = ctypes.c_void_p
for n, res, args in [
    ("pyx_init", None, []), ("pyx_fib", I, [I]), ("pyx_inc", I, [I]), ("pyx_check", I, [I]),
    ("pyx_shout", P, [P]), ("pyx_counts", P, [P]), ("pyx_total", I, [P]), ("pyx_remember", I, [P]),
    ("pyx_hello", None, [P]), ("pyx_strlen", I, [P]), ("pys_str", P, [ctypes.c_char_p, I]),
]:
    f = getattr(lib, n)
    f.restype = res
    f.argtypes = args


def to_pys(s: str) -> int:
    b = s.encode("utf-8", "surrogatepass")
    return lib.pys_str(b, len(b))


def from_pys(p: int) -> str:
    n = I.from_address(p).value          # Str { I len; char s[]; }
    return ctypes.string_at(p + 8, n).decode("utf-8", "surrogatepass")


def deep(k: int, fn):
    # each level goes through a C call (map -> eval loop), so the C stack really grows
    return list(map(lambda j: deep(j, fn), [k - 1]))[0] if k else fn()


t = sys.argv[1]
if t == "basic":
    lib.pyx_init()
    print("fib(20) =", lib.pyx_fib(20))
    print("shout('héllo') =", repr(from_pys(lib.pyx_shout(to_pys("héllo")))))
    print("strlen('héllo') =", lib.pyx_strlen(to_pys("héllo")), "(CPython len:", len("héllo"), ")")
    print("total('a b a') =", lib.pyx_total(to_pys("a b a")))
    print("check(21) =", lib.pyx_check(21))
elif t == "raise":
    lib.pyx_init()
    try:
        print("check(-1) =", lib.pyx_check(-1))
    except BaseException as e:      # never reached: the runtime exits the process
        print("caught", type(e).__name__, e)
    print("after check(-1)")
elif t == "overflow":
    lib.pyx_init()
    print("inc(2**63-1) =", lib.pyx_inc(2**63 - 1))
    print("after")
elif t == "gc_shallow_init":
    # init from the top level, call from deeper: the scan range covers the call (works)
    lib.pyx_init()
    def go():
        r = 0
        for i in range(200):
            r += lib.pyx_total(to_pys("x yy zzz x yy x " * 20))
        return r
    print("deep call total sum:", deep(150, go))
elif t == "gc_deep_init":
    # init deep in the C stack, call from the top: the call's frames are above gc_bottom
    deep(150, lambda: lib.pyx_init())
    r = 0
    for i in range(200):
        r += lib.pyx_total(to_pys("x yy zzz x yy x " * 20))
    print("shallow call total sum:", r, "expected", 200 * 20 * (3 * 1 + 2 * 2 + 1 * 3))
elif t == "gc_held":
    # a Pystachy Str held only by Python (ctypes int) across calls that collect
    lib.pyx_init()
    s = lib.pyx_shout(to_pys("keep me"))
    for i in range(2000):
        lib.pyx_remember(to_pys("k" * (i % 50)))
    print("held str:", repr(from_pys(s)))
elif t == "stdout":
    lib.pyx_init()
    print("py: 1")
    lib.pyx_hello(to_pys("2"))
    print("py: 3")
    sys.stdout.flush()
    lib.pyx_hello(to_pys("4"))
    print("py: 5")
elif t == "sigint":
    import signal
    lib.pyx_init()
    try:
        os.kill(os.getpid(), signal.SIGINT)
        time.sleep(0.2)
        print("no KeyboardInterrupt?")
    except KeyboardInterrupt:
        print("caught KeyboardInterrupt in Python (good)")
    print("still alive")
elif t == "bench":
    lib.pyx_init()
    N = 1_000_000
    f = lib.pyx_inc
    t0 = time.perf_counter()
    for i in range(N):
        f(i)
    t1 = time.perf_counter()
    print(f"ctypes inc: {(t1 - t0) / N * 1e9:.1f} ns/call")
    t0 = time.perf_counter()
    for _ in range(5):
        r = lib.pyx_fib(25)
    t1 = time.perf_counter()
    print(f"ctypes fib(25)={r}: {(t1 - t0) / 5 * 1e3:.3f} ms")
