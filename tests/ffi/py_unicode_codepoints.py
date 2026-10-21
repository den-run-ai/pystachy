# UTF-8 byte lengths at the CPython boundary remain separate from len(str).
# The harness compares this with tools/rt_cpython, under collection stress.
import os
import sys
from pyobj import import_module, of_int, of_str

for s in ["", "ascii", "é", "AéB", "é中🚀", "e\u0301", "\0é\0", "\ud800", "\udfff"]:
    p = of_str(s)
    assert str(p) == s
    assert len(p) == len(s)
    print(ascii(s), len(p))
    p.close()

embedded_sys = import_module("sys")
argv = embedded_sys.attr("argv")
assert len(argv) == len(sys.argv)
for i in range(1, len(sys.argv)):
    arg = argv[of_int(i)]
    assert str(arg) == sys.argv[i]
    print("argument", ascii(str(arg)), len(arg))
    arg.close()

# Also run this file from a Unicode directory when checking the path boundary.
path = embedded_sys.attr("path")[of_int(0)]
script = os.path.realpath(sys.argv[0])
directory = script[:script.rfind("/")] if script.rfind("/") > 0 else "/"
assert str(path) == directory
print("script directory", True)
path.close()
argv.close()
embedded_sys.close()
