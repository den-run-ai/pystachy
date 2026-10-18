# Latin-1 I/O decodes to code points; chr() constructs characters that encode separately.
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/dev.txt"
os.system("printf 'Gr\\374\\337e' > '" + p + "'")
w = open(p, encoding="latin-1").read()
print(w, w == "Grüße", len(w), ord(w[2]))
f = open(p, encoding="latin-1")
print(repr(f.read(2)), len(f.read(1)), len(f.read(2)), repr(f.read()))
f.close()
f = open(p, "w", encoding="latin-1")
print(f.write(chr(195) + chr(169)), f.write(chr(195) + "x"))
f.close()
f = open(p, encoding="latin-1")
b: list[int] = []
c = f.read(1)
while c != "":
    b.append(ord(c))
    c = f.read(1)
f.close()
print(b)
os.remove(p)
os.rmdir(d)
