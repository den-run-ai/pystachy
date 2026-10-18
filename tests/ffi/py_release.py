# Objects dropped without close(): their Python references are released after collections
import sys
from pyobj import import_module, of_int

n = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
blocks = import_module("sys").attr("getallocatedblocks")
before = blocks.call([]).to_int()
for i in range(n):
    of_int(i + 1000000)  # a new PyLong each time, never closed
after = blocks.call([]).to_int()
print("dropped", n, "objects; CPython blocks bounded:", after - before < 5000)
