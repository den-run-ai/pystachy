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
