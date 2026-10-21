# wcwidth's wcwidth() and wcswidth() on the edge cases its port met: the code points at both ends
# of every range of the tables wcwidth() searches, a sample of all code points, text whose UTF-8
# has bytes 0x80-0x9F (the C1 controls' values, which wcswidth() took for controls when it indexed
# bytes), controls, grapheme clusters, n= at and around their boundaries, ambiguous_width
# clamped from the extremes of 64-bit ints, long text, a wcwidth() of two characters, text of
# chr() bytes and the names of `from wcwidth import *`.
# "%c" % cp makes the character cp (chr(cp) below 256 is a byte in Pystachy).
from wcwidth import *
from wcwidth import wcswidth, wcwidth
from wcwidth._constants import _AMBIGUOUS_TABLE, _WIDE_EASTASIAN_TABLE, _ZERO_WIDTH_TABLE

# both ends of each range, and their neighbours, at both ambiguous widths
for name, table in [("zero", _ZERO_WIDTH_TABLE), ("wide", _WIDE_EASTASIAN_TABLE),
                    ("ambiguous", _AMBIGUOUS_TABLE)]:
    hist = [0, 0, 0, 0]
    acc = 0
    n = 0
    for lo, hi in table:
        for cp in [lo - 1, lo, hi, hi + 1]:
            if 0 <= cp <= 0x10FFFF:
                c = "%c" % cp
                w1 = wcwidth(c)
                w2 = wcwidth(c, "auto", 2)
                hist[w1 + 1] += 1
                acc = (acc * 7 + w1 * 4 + w2 + 5) % 1000000007
                n += 1
    print(name, len(table), n, hist, acc)

# every 37th code point, surrogates included
hist1 = [0, 0, 0, 0]
hist2 = [0, 0, 0, 0]
acc = 0
for cp in range(0, 0x110000, 37):
    w1 = wcwidth("%c" % cp)
    w2 = wcwidth("%c" % cp, ambiguous_width=2)
    hist1[w1 + 1] += 1
    hist2[w2 + 1] += 1
    acc = (acc * 3 + w1 + 1) % 1000000007
print("sample", hist1, hist2, acc)

# controls: C0, DEL and C1 are -1, NUL is 0; in text, any of them makes the width -1
ctl = [wcwidth("%c" % cp) for cp in range(0, 0x20)]
ctl += [wcwidth("%c" % cp) for cp in range(0x7F, 0xA1)]
print("controls", ctl)
print("in text", [wcswidth("a%cb" % cp) for cp in [0, 1, 9, 10, 27, 0x7F, 0x80, 0x85, 0x9F, 0xA0]])
print("ascii", wcswidth(""), wcswidth(" ~"), wcswidth("tab\there"), wcswidth("abc\x1bdef"))

# text with UTF-8 continuation bytes 0x80-0x9F, which the port's character split keeps whole
for s in ["\u00e9", "caf\u00e9", "\u4e2d\u6587", "\u00c6sop", "\u0410\u0411", "\u20ac",
          "\U0001f600", "\u0100\u011f", "\u0420\u0435\u0434", "\u3000\uff01"]:
    print(repr(s), wcswidth(s), wcswidth(s, ambiguous_width=2))
print("long", wcswidth("\u00e9" * 100), wcswidth("\u00e9" * 100, ambiguous_width=2),
      wcswidth("\u4e2d" * 1000 + "x"), wcswidth("\u4e2d" * 1000 + "x", 999))

# grapheme clusters: combining marks first, VS16 and VS15 without a base, lone and paired
# regional indicators, ZWJ chains, virama conjuncts, a tag sequence, Thai, fullwidth
for s in ["\u0301abc", "\ufe0fx", "\ufe0ex", "\U0001f1fa",
          "\U0001f1fa\U0001f1f8\U0001f1ec\U0001f1e7", "\U0001f1fa\U0001f1f8\U0001f1ec", "a\u200d",
          "\u200d\u200d", "\u0915\u094d", "\u0915\u094d\u200d\u0937", "\uac01", "\U0001f3fb",
          "x\U0001f3fb", "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f",
          "\U0001f469\U0001f3fd\u200d\U0001f4bb", "\u2764\ufe0e\ufe0f", "\u231a\ufe0e",
          "\u231a\ufe0f", "\u2764\ufe0f", "\u2764", "a\u0308\u0327\u0301", "\u0e01\u0e33",
          "\u0e01\u0e33\u0e33", "\uff21\uff22\uff23", "\u00ad", "\u00a1\u00a1", "\U000e0001",
          "\U0010fffd", "\U00020000"]:
    print(repr(s), wcswidth(s), wcswidth(s, ambiguous_width=2), wcswidth(s, 2), wcswidth(s, 1))

# n= counts characters: at and around the boundaries of a ZWJ family, past the end, negative
fam = "\U0001f468\u200d\U0001f469\u200d\U0001f467ab\u4e2d"
for n in [0, 1, 2, 3, 4, 5, 6, 7, 8, 100, -1, 9223372036854775807]:
    print("n", n, wcswidth(fam, n), wcswidth("abc\x01def", n),
          wcswidth("\u00a1\u00b1x", n, ambiguous_width=2), wcswidth("\u00e9\u00e9\u00e9", n),
          wcswidth(fam, n, "auto", 2))

# ambiguous_width is clamped to 1 or 2
for aw in [0, 1, 2, 3, -9223372036854775807, 9223372036854775807]:
    print("aw", aw, wcswidth("\u00a1\u00b1\u4e2d", ambiguous_width=aw),
          wcwidth("\u00a1", "auto", aw), wcwidth("\u4e2d", ambiguous_width=aw),
          wcwidth("a", ambiguous_width=aw))

# wcwidth() takes one character: ord() of more raises TypeError
for s in ["ab", "\u4e2dx", "\u00e9\u00e9"]:
    try:
        print(wcwidth(s))
    except TypeError as e:
        print("TypeError", e)

# chr(i) below 256 is one byte in Pystachy, the code point i in CPython: in text, a byte that does
# not start a well-formed UTF-8 sequence is one character, which ord() reads as the code point i
for bs in [[0xE9], [0xE9, 0x61, 0x62], [0xC0, 0x61], [0xC3, 0x41], [0xF0, 0x41, 0x42, 0x43],
           [0xE0, 0x80, 0x80], [0xE0, 0x9F, 0xBF], [0xF4, 0x90, 0x80, 0x80], [0xF5, 0xA0],
           [0xE4, 0xB8], [0xE4, 0xB8, 0x41], [0xA1, 0xD7, 0xF7], [0x85, 0x41], [0xFF, 0xFE]]:
    s = "".join([chr(b) for b in bs])
    print("bytes", bs, wcswidth(s), wcswidth("x" + s + "\u4e2d"), wcswidth(s, 1),
          wcswidth(s, None, "auto", 2))

# from wcwidth import * takes the names of __all__
print("star", wcswidth("\u4e2d\u00e9"), wcwidth("\u00a1", "auto", 2), list_versions())
