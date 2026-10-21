# A Latin-1 file's bytes are its characters (encoding="latin-1" or an alias), which the str read
# holds as it holds a literal's: the text equals the literal, prints as UTF-8, and compares,
# splits and formats as text. readline(), iteration, read(), read(n) (n characters, one byte
# each) and readlines() read it so, with newline translation as in any file. printf writes the
# file's bytes.
import os
import tempfile

d = tempfile.mkdtemp()
p = d + "/word.txt"
os.system("printf 'Gr\\374\\337e\\n\\251 caf\\351\\r\\nna\\357ve \\253\\273\\n\\377 end' > '" + p + "'")
with open(p, encoding="latin-1") as f:
    w = f.readline()
print(w, end="")
print(repr(w), ascii(w))
print(w == "Grüße\n", "ü" in w, w.startswith("Grü"), w.endswith("ße\n"), w.rstrip() == "Gr\xfc\xdfe", w < "Grz")
print(f"[{w.rstrip():>7}] [{w.rstrip():*^9}] [{w.rstrip()!r:8}]")
print(w.rstrip().split("ü"), w.rstrip().replace("ß", "ss"), {"Grüße": 1}.get(w.rstrip(), 0), "%s|%-6s|" % (w.strip(), w.strip()))
with open(p, encoding="iso8859-1") as f:
    for line in f:
        print(repr(line), line.strip() in ["Grüße", "© café", "naïve «»", "ÿ end"])
with open(p, encoding="ISO-8859-1", newline="") as f:
    print(repr(f.read()))
f = open(p, encoding="L1")
print(repr(f.read(3)), repr(f.read(2)), repr(f.read(1)), repr(f.readline()), repr(f.read(4)))
print([ord(f.read(1)) for i in range(4)], repr(f.read()), repr(f.read(1)), repr(f.readline()))
f.close()
print(open(p, encoding="cp819").readlines())
print(open(p, encoding="latin1", newline="\r\n").readlines())
print(max(open(p, encoding="latin")), "naïve «»\n" in list(open(p, encoding="8859")))

# UTF-8 bytes read as Latin-1 are a character each
u = d + "/utf8.txt"
with open(u, "w", encoding="utf-8") as f:
    f.write("é€\n")
with open(u, encoding="latin-1") as f:
    t = f.read()
print(repr(t), t == "\xc3\xa9\xe2\x82\xac\n", t == "é€\n")

# an empty file, and a big one (read() takes it in 64 KiB pieces)
e = d + "/empty.txt"
open(e, "w", encoding="latin-1").close()
with open(e, encoding="latin-1") as f:
    print(repr(f.read()), repr(f.readline()), repr(f.read(3)), f.readlines(), [x for x in f])
b = d + "/big.txt"
with open(b, "w", encoding="latin-1") as f:
    print(f.write("é" * 70000 + "\nü"))
with open(b, encoding="latin-1") as f:
    print(f.readline() == "é" * 70000 + "\n", f.read() == "ü")
with open(b, encoding="latin-1") as f:
    print(f.read() == "é" * 70000 + "\nü")
with open(b, encoding="latin-1") as f:
    print(f.read(69999) == "é" * 69999, repr(f.read(3)))
for x in [p, u, e, b]:
    os.remove(x)
os.rmdir(d)
