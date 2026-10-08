# Documented deviation: in a "+" file, a write after reads goes where CPython's text layer
# stopped reading ahead. Pystachy counts that in 8 KiB chunks; CPython's read(n) reads ahead
# by n characters (times its bytes-per-character estimate) when that is more, so after
# read(10000) its write goes at 10000 and Pystachy's at 16384.
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/big.txt"
f = open(p, "w")
f.write("abcdefghi\n" * 3000)
f.close()
f = open(p, "r+")
print(len(f.read(10000)))
f.write("XYZ")
f.close()
g = open(p)
print(g.read().find("XYZ"))
g.close()
os.remove(p)
os.rmdir(d)
