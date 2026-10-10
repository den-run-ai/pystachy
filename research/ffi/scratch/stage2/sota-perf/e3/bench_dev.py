import sys, time, importlib
d = sys.argv[1]
t = time.perf_counter(); sys.path.insert(0, d); m = importlib.import_module("spikemod"); ti = time.perf_counter() - t
def best(f, r=5):
    b = 1e9
    for _ in range(r):
        t = time.perf_counter(); f(); b = min(b, time.perf_counter() - t)
    return b
fib = best(lambda: m.fib(25))
N = 1_000_000
def lp():
    f = m.inc
    for i in range(N): f(i)
def le():
    for i in range(N): pass
inc = (best(lp) - best(le)) / N
print(f"{d}: import {ti*1e3:.2f} ms  fib(25) {fib*1e3:.3f} ms  inc {inc*1e9:.1f} ns/call")
