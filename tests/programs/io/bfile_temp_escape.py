# A binary file used in one expression is closed after it (bfile_temp), except where the call returns
# the file itself, as __iter__() and __enter__() do: that file stays open, as CPython's does while the
# result refers to it. A call on such a result closes the file after it
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/f"
with open(p, "wb") as f:
    f.write(b"line1\nline2\n")
g = open(p, "rb").__iter__()
print(g.closed)
print(g.readline())
print(next(g))
g.close()
h = open(p, "rb").__enter__()
print(h.closed)
print(h.read())
h.close()
print(open(p, "wb").__enter__().write(b"one\n"))
print(open(p, "rb").__iter__().readline())
print(open(p, "rb").read())
os.remove(p)
os.rmdir(d)
