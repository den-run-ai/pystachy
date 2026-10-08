# Documented deviation: when a for loop over a "+" file stops before the end, CPython 3.13 keeps
# the text it read ahead across a write, so the next read() returns that old text
# ('line2\nline3\n' here). Pystachy reads on from where the write ended.
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/it.txt"
f = open(p, "w")
f.write("line1\nline2\nline3\n")
f.close()
f = open(p, "r+")
for line in f:
    print(repr(line))
    break
f.write("XY")
print(repr(f.read()))
f.close()
print(repr(open(p).read()))
os.remove(p)
os.rmdir(d)
