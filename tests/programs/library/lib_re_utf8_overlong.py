# chr(128..255) makes one byte in Pystachy, so bytes that chr() made can spell an overlong UTF-8
# form or a value past U+10FFFF. ord() and repr() read each such byte as its own character (as
# CPython reads the characters chr() made), and re and fnmatch must too (#513).
import fnmatch
import re


def raw(bs: list[int]) -> str:
    return "".join([chr(b) for b in bs])


def chars(t: str) -> int:
    # the characters ord() counts in t
    try:
        ord(t)
        return 1
    except TypeError as e:
        return int(str(e).split("length ")[1].split(" ")[0])


for bs in [[0xF4, 0x90, 0x80, 0x80], [0xE0, 0x80, 0x80], [0xF0, 0x80, 0x80, 0x80]]:
    t = raw(bs)
    print(len(t), len(re.findall(".", t)), fnmatch.fnmatchcase(t, "?"),
          fnmatch.fnmatchcase(t, "?" * len(bs)))


def strict(bs: list[int]) -> bool:
    # whether bs is one character to ord(): a lead byte from 0xC2 to 0xF4 with its continuation
    # bytes, neither overlong nor past U+10FFFF (a surrogate is one)
    b = bs[0]
    k = 2 if 0xC2 <= b < 0xE0 else 3 if 0xE0 <= b < 0xF0 else 4 if 0xF0 <= b < 0xF5 else 1
    if k == 1 or k != len(bs):
        return False
    v = b & (0x7F >> k)
    for x in bs[1:]:
        if x & 0xC0 != 0x80:
            return False
        v = (v << 6) | (x & 0x3F)
    return (0x80 if k == 2 else 0x800 if k == 3 else 0x10000) <= v <= 0x10FFFF


DOT = re.compile("(?s).")


def agrees(bs: list[int]) -> bool:
    # re's subject decoder (also bounded by endpos), its pattern decoder and fnmatch's count the
    # characters ord() counts: in CPython, len(t); in Pystachy, one for a strict sequence, else len(t)
    t = raw(bs)
    n = chars(t)
    if n != len(t) and not (n == 1 and strict(bs)):
        return False
    return (len(DOT.findall("a" + t + "b")) == n + 2
            and len(DOT.findall(t, 0, len(t) - 1)) == (n - 1 if n == len(t) else 0)
            and len(re.findall("[" + t + "]", t)) == n
            and fnmatch.fnmatchcase(t, "?" * n) and not fnmatch.fnmatchcase(t, "?" * (n + 1))
            and fnmatch.fnmatchcase(t, ("[" + t + "-" + t + "]") * n))


# Every lead byte from 0xC0, alone and with continuations at each boundary: 0x7FF/0x800 (E0 9F BF,
# E0 A0 80), 0xFFFF/0x10000 (F0 8F BF BF, F0 90 80 80), 0x10FFFF/0x110000 (F4 8F BF BF, F4 90 80 80)
# and the surrogates (ED A0 80 to ED BF BF); a sequence of three or four bytes also one byte short.
# (The caches are cleared, and this runs first, for a small heap where every allocation collects.)
for lead in range(0xC0, 0x100):
    re.purge()
    fnmatch._compile_pattern.cache_clear()
    k = 2 if lead < 0xE0 else 3 if lead < 0xF0 else 4
    seqs = [[lead]]
    for second in [0x80, 0x8F, 0x90, 0x9F, 0xA0, 0xBF]:
        bs = [lead, second] + [0x80 if second in [0x80, 0x90, 0xA0] else 0xBF] * (k - 2)
        seqs.append(bs)
        if k > 2:
            seqs.append(bs[:-1])
    good = 0
    for bs in seqs:
        if agrees(bs):
            good += 1
    print("lead", hex(lead), len(seqs), good)

# The APIs on overlong forms and values past U+10FFFF (and a lead byte above 0xF4, and C1)
CASES = [[0xE0, 0x80, 0x80], [0xE0, 0x9F, 0xBF], [0xE0, 0x85, 0xA0], [0xF0, 0x80, 0x80, 0x80],
         [0xF0, 0x8F, 0xBF, 0xBF], [0xF4, 0x90, 0x80, 0x80], [0xF4, 0xBF, 0xBF, 0xBF],
         [0xF7, 0xBF, 0xBF, 0xBF], [0xC1, 0xBF]]
for bs in CASES:
    t = raw(bs)
    n = len(t)
    print(ascii(t), chars(t), [m.span() for m in re.finditer(".", t)], len(re.findall(".", "é" + t + "€")))
    print("search", re.search(t[1:], "x" + t + "y").span(), re.match(t, t + "z") is not None,
          re.fullmatch(t, t) is not None, re.fullmatch(t[:-1], t) is None,
          re.fullmatch(re.escape(t), t) is not None)
    print("sub", len(re.sub(".", "<\\g<0>>", t)) == 3 * n, re.subn("(?s).", "", t)[1],
          [len(p) for p in re.split(t[1], "a" + t + "b")], len(re.split("(?=.)", t)))
    rx = re.compile(".")
    print("pos", [m.span() for m in rx.finditer(t, 1, n - 1)], rx.findall(t, 2) == [c for c in t[2:]],
          rx.search(t, n - 1).span(), rx.match(t, 1, 1) is None)
    print("classes", len(re.findall("[\\x80-\\xbf]", t)), len(re.findall("[^\\x80-\\xbf]", t)),
          len(re.findall("[" + t[0] + "]", t)), len(re.findall("[^" + t[0] + "]", t)),
          len(re.findall("[" + t + "]", t)), len(re.findall("(?i)[\\xc0-\\xde]", t)),
          len(re.findall("\\w", t)), len(re.findall("\\s", t)), len(re.findall("\\b", "a" + t)))
    g = re.fullmatch("(.)(.*)", t)
    print("groups", g.span(1), g.span(2), re.search("(?<=" + t[0] + ").", t).span(),
          re.fullmatch("(" + t[0] + ")" + t[1:] + "\\1?", t) is not None)
    names = [t, t[:-1], t[1:], t + "a", "a", chr(0xE0), "é", "😀"]
    print("fnmatch", fnmatch.fnmatchcase(t, "?"), fnmatch.fnmatchcase(t, "?" * n), fnmatch.fnmatchcase(t, t),
          fnmatch.fnmatchcase(t, "*" + t[-1]), fnmatch.fnmatchcase(t, "[!a-z]" * n),
          fnmatch.filter(names, "?" * n) == [t], len(fnmatch.filter(names, t[0] + "*")))
    for pat in ["[" + t + "-a]", "[a-" + t + "]", "[" + t[0] + "-" + t[-1] + "]", "[!" + t + "-a]",
                "[" + t + "-" + t + "]", "[" + t[:2] + "-\x7f]", "[\x01-" + t + "]"]:
        print(ascii(fnmatch.translate(pat)), [fnmatch.fnmatchcase(name, pat) for name in names])

# A surrogate's three bytes are one character to ord(), and so to re and fnmatch.
for s in [chr(0xD800), chr(0xDBFF) + "a", chr(0xDFFF)]:
    print("surrogate", len(re.findall(".", s)), fnmatch.fnmatchcase(s, "?" * len(re.findall(".", s))))
