# Writing a Latin-1 file: each character of the text is its byte (U+0000 to U+00FF; a byte chr()
# makes is one too), and write() returns the number of characters, without the "\r"s that newline
# translation adds. A character above U+00FF raises CPython's UnicodeEncodeError, a ValueError
# naming the first run of such characters by their position in the text (as translated), before
# any of that text reaches the file: what earlier writes gave stays, and a "+" file's position
# does not move. dump() shows the bytes written, read back one character (byte) at a time
# (io_latin1_read.py reads bytes that printf wrote).
import os
import tempfile


def dump(path: str) -> None:
    f = open(path, encoding="latin-1", newline="")
    out: list[str] = []
    c = f.read(1)
    while c != "":
        out.append(f"{ord(c):02x}")
        c = f.read(1)
    f.close()
    for i in range(0, len(out), 16):
        print(" ".join(out[i : i + 16]))
    print(len(out), "bytes")


d = tempfile.mkdtemp()
p = d + "/out.txt"
with open(p, "w", encoding="latin-1") as f:
    print(f.write("Grüße\n"), f.write(""), f.write("© ÿ\n"), f.write(chr(233) + "x" + chr(128) + "\n"))
    print("é", 1, file=f)
    f.writelines(["ä\n", "ö\n"])
dump(p)
with open(p, "w", encoding="iso-8859-1", newline="\r\n") as f:
    print(f.write("a\nü\n"))
dump(p)
with open(p, "w", encoding="L1", newline="\r") as f:
    print(f.write("ß\n"))
dump(p)
every = "".join(["%c" % i for i in range(256)])
with open(p, "w", encoding="latin-1") as f:
    print(f.write(every))
dump(p)
with open(p, encoding="latin-1", newline="") as f:
    print(f.read() == every)

# characters it cannot encode
f = open(p, "w", encoding="latin-1")
f.write("ok\n")
for t in ["5 €\n", "äöü€x", "€€ and ō", "x" + chr(0x1F600) + "y", "a" + chr(0xD800), "'\"" + chr(0x101)]:
    try:
        print(f.write(t))
    except UnicodeEncodeError as e:
        print(e)
        print(repr(e), type(e).__name__)
try:
    f.write("Āb")
except ValueError as e:
    print("ValueError:", e)
try:
    f.write("Ab€")
except UnicodeError as e:
    print("UnicodeError:", e)
try:
    print("p", "€", "q", file=f)
except UnicodeEncodeError as e:
    print("print:", e)
try:
    f.writelines(["1\n", "2€\n", "3\n"])
except UnicodeEncodeError as e:
    print("writelines:", e)
print(f.write("end\n"))
f.close()
dump(p)
with open(p, "w", encoding="latin-1", newline="\r\n") as f:
    try:
        f.write("a\nb\n€")
    except UnicodeEncodeError as e:
        print(e)
    try:
        f.write("\n\n" + chr(0x2028) + chr(0x2029))
    except UnicodeEncodeError as e:
        print(e)
dump(p)
# a closed file, and one open for reading, fail before the text is encoded
try:
    f.write("€")
except ValueError as e:
    print(e)
try:
    open(p, encoding="latin-1").write("€")
except ValueError as e:
    print(e)

# a "+" file: a failed write moves nothing
with open(p, "w", encoding="latin-1") as f:
    f.write("abcdéf\nline2\n")
with open(p, "r+", encoding="latin-1") as f:
    print(repr(f.read(2)))
    try:
        f.write("€")
    except UnicodeEncodeError as e:
        print(e)
    print(repr(f.read()), f.write("Z"))
with open(p, "a+", encoding="latin-1") as f:
    try:
        f.write("ok€")
    except UnicodeEncodeError as e:
        print(e)
    print(f.write("ÿ\n"))
dump(p)
os.remove(p)
os.rmdir(d)
