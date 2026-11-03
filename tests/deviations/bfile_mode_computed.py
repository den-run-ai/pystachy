# Documented deviation: open() of a binary mode that the program computes raises
# NotImplementedError (lib/compatibility.md#binary-files): the compiler makes a binary file of
# open() only where its mode is a literal, as the file's class depends on it, and this open()
# makes a text file. CPython opens the file and reads b'data'
import os
import tempfile

d = tempfile.mkdtemp()
p = os.path.join(d, "c.bin")
with open(p, "wb") as f:
    f.write(b"data")
mode = "r" + "b"
try:
    g = open(p, mode)
    print(g.read())
except NotImplementedError as e:
    print("NotImplementedError", e)
