# dropped Objects holding large Python objects: each counts as its size (sys.getsizeof) in the
# collector's accounting, so peak memory stays near CPython's (tests/ffi/run.sh runs this one
# without GC stress)
from pyobj import import_module, of_int

b = import_module("builtins")
res = import_module("resource")
n = 0
for i in range(1500):
    chunk = b.attr("bytearray").call([of_int(1 << 20)])
    n += len(chunk)
print(n)
rss = res.attr("getrusage").call([res.attr("RUSAGE_SELF")]).attr("ru_maxrss").to_int() // 1024
print("peak below 200 MiB:", rss < 200)
