import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx
mode, N = sys.argv[1], int(sys.argv[2])
S = object()
def cb_naive():
    y = S                      # a local reference the skipped frame should release
    fx.check_naive(-1)         # Pystachy raise with no boundary: forced unwind through CPython
    print("never")
def cb_boundary():
    y = S
    fx.check(-1)               # boundary: Python ValueError
cb = cb_naive if mode == "naive" else cb_boundary
r0 = sys.getrefcount(S)
res = {}; first_err = None
for i in range(N):
    try:
        r = fx.apply(cb)
        res[r] = res.get(r, 0) + 1
    except BaseException as e:
        k = type(e).__name__; res[k] = res.get(k, 0) + 1
        if first_err is None: first_err = (i, repr(e)[:80])
print("mode", mode, "N", N, "results", res, "first error at", first_err)
print("refcount(S) before", r0, "after", sys.getrefcount(S), " C depth counter", fx.depth())
def deep(n): return 0 if n == 0 else 1 + deep(n - 1)
try: print("deep(200) =", deep(200))
except RecursionError as e: print("deep(200) ->", repr(e))
f = sys._getframe(); n = 0
while f: n += 1; f = f.f_back
print("python frames visible from top level:", n)
