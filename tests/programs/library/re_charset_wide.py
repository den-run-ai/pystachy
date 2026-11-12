# Character sets with characters past Latin-1 (a big charset) and past the BMP.
import re

P1 = re.compile(r"[^\"'\\„“”{}\[\](),:`]+")
P2 = re.compile(r"[{\[(#/" + re.escape("".join(['"', "'", "“", "”"])) + "]")
P3 = re.compile("[a-zα-ωа-я一-鿿\U0001F600-\U0001F64F_]+")
for text in ["plain run, then", "„quoted“ text", "x{y", "“start", "héllo wörld: 1", "日本語のテキスト,", "mixed😀emoji🙂 z"]:
    m = P1.match(text)
    s = P2.search(text)
    w = P3.findall(text.lower())
    print(repr(text), m.group() if m else None, s.start() if s else None, w)


# Sets whose runs cross the Latin-1 and BMP bounds, merge, or leave the BMP; negated ones too.
SETS = [
    "[a\u0100]", "[\u00fe-\u0101]", "[\u0100-\u0102\u0103-\u0105]", "[a-c\u0100-\u0105x]",
    "[a\u0100\u0200\u0300]", "[^a\u0100\u0200\u0300]", "[\u0100-\uffff]", "[\u00ff-\U00010005]",
    "[\U00010000-\U00010010b\u0101]", "[^\u0100-\U0010ffff]", "[\u0100\u0100\u0101a]",
    "[\\w\u0100\u2028]", "[\u01ff\u0200\u02ff\u0300\uffff]", "[\u0000-\u00ff\u0101\u0103]",
]
TEXT = "ab\u00fe\u00ff\u0100\u0101\u0102\u0105\u01ff\u0200\u02ff\u0300 x_\u2028\uffff\U00010000\U00010005\U00010011\U0010ffff"
for source in SETS:
    hits = re.findall(source, TEXT)
    print(ascii(source), [hex(ord(h)) for h in hits])
