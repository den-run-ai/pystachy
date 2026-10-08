# What another handle sees of a file being written: CPython keeps written text pending until
# 8 KiB have gathered (a write of 8 KiB or more goes at once, after what was pending), then
# hands it to a buffer of st_blksize bytes, or buffering= bytes, which keeps a piece smaller
# than its free space; buffering=1 flushes each write holding "\n" or "\r"; newline= counts
# the translated bytes.
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/buf.txt"


def seen() -> int:
    r = open(p)
    n = len(r.read())
    r.close()
    return n


w = open(p, "w")
w.write("x" * 5000)
a = seen()
w.write("y" * 3191)
b = seen()
w.write("z")
c = seen()
w.write("q" * 100)
print(a, b, c, seen())
w.write("r" * 9000)
print(seen())
print("line", file=w)
w.flush()
print(seen())
w.close()
w = open(p, "w", buffering=1)
w.write("no newline")
a = seen()
w.write(" then one\n")
b = seen()
w.write("and a return\r")
c = seen()
print(a, b, c, "and", "more", file=w, sep="|")
print(seen())
w.close()
w = open(p, "w", buffering=10000)
w.write("s" * 8192)
a = seen()
w.write("t" * 1000)
b = seen()
w.write("u" * 7192)
c = seen()
w.write("v" * 20000)
print(a, b, c, seen())
w.close()
w = open(p, "w", newline="\r\n")
w.write("\n" * 4095)
a = seen()
w.write("\n")
print(a, seen())
w.close()
w = open(p, "a+")
w.write("appended")
print(repr(w.read()), seen())
w.close()
os.remove(p)
os.rmdir(d)
