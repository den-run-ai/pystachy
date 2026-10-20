# str.isspace(), strip(), split() and rsplit() know CPython's Unicode whitespace, character by
# character: bytes of other characters (U+0160 is C5 A0, U+0145 is C5 85) are not whitespace
SPACES = "\t\n\x0b\x0c\r\x1c\x1d\x1e\x1f \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"


def show(s: str) -> None:
    print(repr(s), repr(s.strip()), repr(s.lstrip()), repr(s.rstrip()), s.isspace())
    print("  ", s.split(), s.rsplit(), s.split(None, 1), s.rsplit(None, 1), s.split(None, 0), s.rsplit(None, 0), s.split(None, 2), s.rsplit(None, 2))


for i in range(0, 0x3001):
    if chr(i).isspace():
        print(f"{i:#x}", end=" ")
print()
show(SPACES)
show("\u3000name = value\u00a0\u2028")
show("\u0160\u0145")
show(" a\u0160b \u2003 c\u0145\u3000d\u205f")
show("x\u2009y\u202fz\U0001f600\u1680")
show("\u00e9t\u00e9\u3000\u00e9t\u00e9")
show(chr(0x85) + "a" + chr(0xa0) + "b" + chr(0x85))
show("")
show("\u200b")  # (a zero width space is no whitespace)
print(" ".isspace(), "\u3000\u2028".isspace(), "a\u3000".isspace(), "".isspace(), "\u0160".isspace())
print(repr("\u00e9a\u00e9".strip("\u00e9")), repr("\u00e9a\u00e8".strip("\u00e8")), repr("\u00e8\u00e9a".lstrip("\u00e9\u00e8")))
print(repr("\U0001f600x\U0001f601".strip("\U0001f600")), repr("--\u2003--".strip("-")), repr("ab\u00e9".rstrip("\u00e9b")))
print(repr("\u0160a\u0160".strip("\u00a0")), repr("\u0160a".strip("\u0160")))
words = "one\u3000two\u2003\u2003three\u00a0four".split()
print(words, len(words))
print("\u2028".join(["a", "b"]).splitlines(), "x\u2029y\x85z".splitlines(True))
