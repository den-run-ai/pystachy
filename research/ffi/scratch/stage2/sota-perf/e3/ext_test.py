import os
import signal
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spikemod as m  # noqa: E402


def deep(k, fn):
    return list(map(lambda j: deep(j, fn), [k - 1]))[0] if k else fn()


t = sys.argv[1]
if t == "basic":
    print("fib(20) =", m.fib(20))
    for s in ["hello", "héllo", "a\x00b", "emoji \U0001F600", "lone \udcff"]:
        r = m.shout(s)
        print(f"shout({s!r}) = {r!r}   strlen={m.strlen(s)} CPython len={len(s)} CPython upper={s.upper() + '!'!r}")
    print("counts =", m.counts("b a b c a b"))
    print("total =", m.total("a b a"))
    print("remember:", [m.remember("x") for _ in range(3)])
elif t == "exceptions":
    for f, a in [(m.check, -5), (m.boom, 1), (m.key, "a b"), (m.inc, 2**63 - 1), (m.inc, 2**64), (m.bye, 3)]:
        try:
            print(f.__name__, repr(a), "->", f(a))
        except BaseException as e:
            print(f.__name__, repr(a), "-> raised", type(e).__name__, repr(e))
    print("check(4) still works:", m.check(4))
elif t == "exc_cost":
    N = 200_000
    t0 = time.perf_counter()
    for i in range(N):
        try:
            m.check(-1)
        except ValueError:
            pass
    t1 = time.perf_counter()
    print(f"raise across boundary: {(t1 - t0) / N * 1e9:.0f} ns per raise+catch")
    def deep_raise():
        t0 = time.perf_counter()
        for i in range(N // 10):
            try:
                m.check(-1)
            except ValueError:
                pass
        return (time.perf_counter() - t0) / (N // 10) * 1e9
    print(f"same, 150 C-level Python frames deep: {deep(150, deep_raise):.0f} ns")
elif t == "gc":
    # init happened at import (top level); call deep and shallow, under PYSTACHY_GC_STRESS
    want = 200 * 20 * (3 * 1 + 2 * 2 + 1 * 3)
    def go():
        return sum(m.total("x yy zzz x yy x " * 20) for _ in range(200))
    print("deep:", deep(150, go) == want, " shallow:", go() == want)
    h = m.shout_handle("keep me")
    for i in range(2000):
        m.remember("k" * (i % 50))
    print("pinned handle survives:", m.handle_str(h))
    del h
    d = m.counts("p q p " * 50)
    print("counts under stress:", d)
elif t == "stdout":
    print("py: 1")
    m.hello("2")
    print("py: 3")
    m.hello("4")
    print("py: 5")
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        m.hello("captured")
    print("redirect_stdout captured:", repr(buf.getvalue()))
elif t == "sigint":
    try:
        os.kill(os.getpid(), signal.SIGINT)
        time.sleep(0.2)
        print("no KeyboardInterrupt?")
    except KeyboardInterrupt:
        print("caught KeyboardInterrupt in Python (good)")
elif t == "reimport":
    a = m.remember("z")
    del sys.modules["spikemod"]
    import spikemod as m2
    print("re-import is a new module object:", m2 is not m, " runtime state kept (remember):", a, "->", m2.remember("z"))
elif t == "bench":
    N = 2_000_000
    for name, f in [("noop (METH_FASTCALL, no call into Pystachy)", m.noop), ("inc", m.inc)]:
        best = 1e9
        for _ in range(3):
            t0 = time.perf_counter()
            for i in range(N):
                f(i)
            best = min(best, (time.perf_counter() - t0) / N * 1e9)
        print(f"ext {name}: {best:.1f} ns/call (incl. ~17 ns loop)")
    s = "hello world " * 4
    t0 = time.perf_counter()
    for i in range(N // 4):
        m.strlen(s)
    print(f"ext strlen(48-char ASCII str): {(time.perf_counter() - t0) / (N // 4) * 1e9:.1f} ns/call")
    t0 = time.perf_counter()
    for i in range(N // 4):
        m.shout(s)
    print(f"ext shout(48-char str) round trip: {(time.perf_counter() - t0) / (N // 4) * 1e9:.1f} ns/call")
    best = 1e9
    for _ in range(5):
        t0 = time.perf_counter()
        r = m.fib(25)
        best = min(best, time.perf_counter() - t0)
    print(f"ext fib(25)={r}: {best * 1e3:.3f} ms")
