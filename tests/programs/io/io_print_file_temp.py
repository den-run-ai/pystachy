# print(..., file=open(p, "w")) closes that file right after the print, as CPython does when
# its last reference goes, so the text is in the file at once
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/t.txt"
print("x", 1, file=open(p, "w"))
print(repr(open(p).read()))
print("y", file=open(p, "a"), end="", flush=True)
print(repr(open(p).read()))
os.remove(p)
os.rmdir(d)
