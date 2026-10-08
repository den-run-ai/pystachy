# The encoding argument of open() takes CPython's names for UTF-8 and Latin-1, normalized as
# its codec lookup does it (lowercase, and a run of other characters than letters, digits and
# "." as one "_" between them), then an alias (or one with "." read as "_") or the codec
# module's own name. read(n) of a Latin-1 file counts bytes, each one a character.
import os
import tempfile

names = ["utf-8", "UTF8", "U8", "utf", "Utf 8", "_utf8_", "utf--8", "utf-8 ", "utf8\xe9", "cp65001", "UTF8-UCS2",
         "utf8_ucs4", "utf_8", "latin-1", "Latin1", "L1", "latin", "iso-8859-1", "ISO 8859-1", "iso8859.1",
         "iso_8859-1:1987", "ISO-IR-100", "8859", "IBM819", "csISOLatin1", "cp819", "iso8859"]
for e in names:
    f = open("/dev/null", "w", encoding=e)
    f.write("x")
    f.close()
    print(repr(e), "ok")
for e in ["UTF-8", "u8", "utf 8", "latin_1", "l1", "iso8859.1", " Latin-1 "]:  # constants are checked when compiling
    print(repr(open("/dev/null", encoding=e).read()), end=" ")
print()
d = tempfile.mkdtemp()
p = d + "/lat.txt"
f = open(p, "w", encoding="latin-1")
f.write(chr(233) + chr(169) + "ab" + chr(128))
f.close()
g = open(p, encoding="latin-1")
print(len(g.read(1)), len(g.read(1)), repr(g.read(2)), len(g.read()), repr(g.read(5)))
g.close()
h = open(p, encoding="L1")
print(ord(h.read(1)), ord(h.read(1)), h.readline() == "ab" + chr(128))
h.close()
os.remove(p)
os.rmdir(d)
