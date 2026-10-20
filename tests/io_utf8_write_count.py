# write() of a UTF-8 text file returns the number of characters it writes, as len() counts them,
# not the number of bytes: without the "\r"s that newline translation adds, in "a" mode, for a
# str built at run time, and for sys.stdout (#120). dump() shows the bytes written.
import sys
import tempfile


def dump(path: str) -> None:
    f = open(path, encoding="latin-1", newline="")
    out: list[str] = []
    c = f.read(1)
    while c != "":
        out.append(f"{ord(c):02x}")
        c = f.read(1)
    f.close()
    print(" ".join(out), len(out), "bytes")


d = tempfile.mkdtemp()
p = d + "/out.txt"
with open(p, "w", encoding="utf-8") as f:
    print(f.write("é"), f.write("Grüße\n"), f.write(""), f.write("日本語"), f.write("😀x"))
    s = "naïve " * 3
    t = "".join([chr(c) for c in [233, 0x20AC, 0x1F600, 65]])
    print(f.write(s), len(s), f.write(t), len(t))
dump(p)
with open(p, "w", encoding="utf-8", newline="\r\n") as f:
    print(f.write("a\né\n"), f.write("\n"), f.write("ü"))
with open(p, "a", encoding="utf-8") as f:
    print(f.write("ß€\n"))
dump(p)
n = sys.stdout.write("ça va, 日本\n")
print(n)
print(sys.stderr.write(""), file=sys.stdout)
