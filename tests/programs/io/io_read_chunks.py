# read(n) takes n characters, whatever bytes they need, also across the 4 KiB its bytes gather in
# before they become the str (#213): UTF-8 characters and "\r\n" that straddle 4096 bytes, in each
# newline mode and for reads of several sizes, read(0), reads after the end, and a file opened for
# update that is read in pieces, then written: the write lands where CPython's would.
import os
import tempfile

d = tempfile.mkdtemp()
p = os.path.join(d, "t.txt")
text = "a" * 4094 + "é" + "ü" * 3000 + "\r\n" + "b" * 4093 + "\r\nc\rd\n" + "日本" * 2000 + "\r"
with open(p, "w", encoding="utf-8", newline="") as f:
    f.write(text)

for nl in [None, "", "\n", "\r", "\r\n"]:
    with open(p, encoding="utf-8", newline=nl) as f:
        expect = f.read()
    for n in [1, 7, 4095, 4096, 4097, 10000]:
        pieces: list[str] = []
        with open(p, encoding="utf-8", newline=nl) as f:
            print(repr(f.read(0)), end=" ")
            while True:
                s = f.read(n)
                if not s:
                    break
                pieces.append(s)
            after = f.read(n)
        print(repr(nl), n, len(pieces), "".join(pieces) == expect, repr(pieces[0][:3]), repr(pieces[-1][-1]), repr(after))

# the characters at the 4096-byte seam, one read each
with open(p, encoding="utf-8", newline=None) as f:
    head = f.read(4093)
    print(head == "a" * 4093, [f.read(1) for i in range(4)], f.read(2999) == "ü" * 2998 + "\n", repr(f.read(2)))

# r+: reads in pieces, then a write, which goes where CPython's text layer has read up to
q = os.path.join(d, "u.txt")
with open(q, "w", encoding="utf-8", newline="") as f:
    f.write(("0123456789" * 1000 + "\n") * 3)
with open(q, "r+", encoding="utf-8") as f:
    first = f.read(5000)
    second = f.read(4096)
    f.write("Z")
with open(q, encoding="utf-8") as f:
    back = f.read()
print(first == ("0123456789" * 500), second[:4], back.count("Z"), back.find("Z"), len(back))
