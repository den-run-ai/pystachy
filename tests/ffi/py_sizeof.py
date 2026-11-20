# an Object whose Python object's size (sys.getsizeof) is near 2**63, as a __sizeof__ that lies
# makes it: the collector counts that size as allocated, a sum that stops at its limit where it
# overflowed, after which no collection started (#1584). The strings dropped after it are
# collected, so peak memory stays near CPython's (tests/ffi/run.sh runs this one without GC
# stress, which would collect anyway)
from pyobj import import_module

m = import_module("side_sizeof")
held = m.attr("Liar").call([])
print("huge:", bool(m.attr("huge").call([held])))
n = 0
for i in range(1000000):
    s = "x" * 300 + str(i)
    n += len(s)
print(n)
res = import_module("resource")
rss = res.attr("getrusage").call([res.attr("RUSAGE_SELF")]).attr("ru_maxrss").to_int() // 1024
print("peak below 200 MiB:", rss < 200)
