# per-call cost of an exported function against the same function in Python (run from a dir with fastmath.*.so)
import sys, timeit
import fastmath as m
def check(n):
    if n < 0:
        raise ValueError(f"negative: {n}")
    return n * 2
N = 2_000_000
loop = min(timeit.repeat("for _ in r: pass", setup=f"r = range({N})", number=1, repeat=5)) / N
ext = min(timeit.repeat("for _ in r: f(4)", setup=f"r = range({N})", globals={"f": m.check}, number=1, repeat=5)) / N
py = min(timeit.repeat("for _ in r: f(4)", setup=f"r = range({N})", globals={"f": check}, number=1, repeat=5)) / N
print(f"{sys.version.split()[0]}{'t' if not getattr(sys, '_is_gil_enabled', lambda: True)() or 'free-threading' in sys.version else ''}: loop {loop*1e9:.1f} ns; ext check(4) {(ext-loop)*1e9:.1f} ns net; python check(4) {(py-loop)*1e9:.1f} ns net")
