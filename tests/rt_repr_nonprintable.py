# repr() escapes every character str.isprintable() rejects, as CPython's unicode_repr does:
# \xhh up to U+00FF, \uhhhh up to U+FFFF, \Uhhhhhhhh above, in containers and f"{x!r}" too
print(repr("a\u00a0b"), ["\u3000", "\x85"], {"\u2066": 1}, ("\u2009", 2))
print(repr("\xa0\xad\u200b\u2028\u2029\ufeff\u3000\U000e0001\U0010ffff\ue000\U0001f600"))
print(["\x7f\x80\x9f\xa0\xa1", "\u00e9", "\u0378", "\U000323af\U000323b0"])
print(f"{'x\x9b'!r} {['\x00', '\u00ad']!r}")
s = "q'\"\\\n\t\r\x1b\u0085"
print(repr(s), ascii(s), repr("'\u00a0"), repr("\"\u00a0'"))
print(repr(chr(0x85)), repr(chr(0xa0)), repr(chr(0xad)), repr(chr(0x2028)), repr(chr(0xd800)), repr(chr(0xdfff)))
for c in [0x377, 0x378, 0x1680, 0x180e, 0x2000, 0x200f, 0x2060, 0x206f, 0xfff9, 0xfffd, 0xfffe, 0x1d173,
          0x1d17b, 0x40000, 0xdffff, 0xe007f, 0xe0100, 0xe01ef, 0xe01f0, 0xf0000, 0x10fffd, 0x10ffff]:
    print(f"{c:#x}", repr(chr(c)))

# where repr() starts and stops escaping: every code point of U+0080..U+323FF and U+E0000..U+E01FF
# (beyond them, Unicode 15.1 has only unassigned and private-use code points)
out: list[str] = []
prev = False
c = 0x80
while c < 0xE0200:
    esc = repr(chr(c))[1] == "\\"
    if esc != prev:
        out.append(f"{c:x}")
        prev = esc
    c = c + 1 if c != 0x323FF else 0xE0000
print(len(out))
print(" ".join(out))
