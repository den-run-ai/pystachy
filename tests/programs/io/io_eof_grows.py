# Reading at the end of a file is not final: CPython reads again, so data another handle
# appends later is seen by readline(), read(n), read(), readlines() and iteration.
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/grow.txt"
w = open(p, "w")
w.write("a\n")
w.flush()
r = open(p)
print(repr(r.readline()), repr(r.readline()), repr(r.read(3)))
w.write("b\nc")
w.flush()
print(repr(r.readline()), repr(r.read(1)), repr(r.read()))
w.write("\nd\n")
w.flush()
print(r.readlines(), repr(r.read()))
w.write("e\nf\n")
w.close()
print([line for line in r])
r.close()
os.remove(p)
os.rmdir(d)
