import time, importlib.util, sys
import fastmath as m
assert m.__file__.endswith(".so")
spec = importlib.util.spec_from_file_location("fm_py", "fastmath.py"); p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
def t(f, *a, n=1_000_000):
    t0 = time.perf_counter()
    for _ in range(n): f(*a)
    return (time.perf_counter() - t0) / n * 1e9
def empty(*a): pass
base = t(lambda *a: None)
for name, f, args in [("ext fib(1)", m.fib, (1,)), ("py fib(1)", p.fib, (1,)), ("ext shout('hello world')", m.shout, ("hello world",)), ("py shout", p.shout, ("hello world",)), ("ext check(3)", m.check, (3,))]:
    print(f"{name}: {t(f, *args):.0f} ns/call (lambda loop {base:.0f})")
for name, f in [("ext fib(90)", m.fib), ("py fib(90)", p.fib)]:
    print(f"{name}: {t(f, 90, n=200000):.0f} ns")
