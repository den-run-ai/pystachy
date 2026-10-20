# The search enters the matcher only where a match may begin: where one of the leading
# alternatives' literals and classes all match, or where literals that every match holds at a
# bounded offset from its start are found. Cover the offsets' bounds, literals at either end or
# cut by endpos, starts before pos, case-insensitive literals, lookaround and anchors before the
# literals, groups, and patterns whose head has no bounded width.
import re


def describe(m: re.Match | None) -> str:
    if m is None:
        return "None"
    return str(m.start()) + ":" + str(m.end()) + " " + repr(m.groups()) + " " + str(m.lastindex)


def run(pattern: str, texts: list[str]) -> None:
    rx = re.compile(pattern)
    print(pattern)
    for t in texts:
        windows = [describe(rx.search(t, p, e)) for p, e in [(1, len(t)), (0, len(t) - 1), (2, 6), (3, 3)]]
        # (split() with groups would give None for those that do not take part: a documented deviation)
        print(" ", repr(t), [describe(m) for m in rx.finditer(t)], windows, rx.sub("<>", t),
              str(rx.split(t)) if rx.groups == 0 else str(rx.subn("#", t, 2)))


# alternatives that all begin with literals and classes
for p in [r"agggtaaa|tttaccct", r"[cgt]gggtaaa|tttaccc[acg]", r"(ab|cd)e", r"((?:ab|a[bc])c)",
          r"(?:ab|ac|a)d?", r"(x)(?:ab|ba)+", r"(?:a\u00e9|\u00e9a|[\u0400-\u04ff]b)", r"(?:ab|c[^c]|.d)x"]:
    run(p, ["tttacccttagggtaaacgggtaaatttacccgx", "abeabcdcde", "xabbaba", "a\u00e9a\u0410b\u00e9a", "abdacacxcdx",
            "", "ab"])

# literals at a bounded offset from every match's start
for p in [r'(^|[^\\])"/Q\((\d+)\)', r"\s?;\s?", r"(?:x|yz)abc", r"(?<=q)abc", r"(?=a)abc", r"\babc\b", r"\Babc",
          r"(?:a|)bc", r".{0,2}abc", r"[ab]{1,3}c", r"(a)?bc", r"(?:(a)|b)c", r"(?!x)ab", r"(?i)abc",
          r"(?ai)abc", r"(?i)\u00e9t\u00e9", r"(?i:x)ABC", r"a(?i:B)c", r"abc$", r"(?m)x$|abc", r"(^abc)",
          r"(?:\Aa|b)bc"]:
    run(p, ['"/Q(12)" a"/Q(3)"\\"/Q(4)"', "; a ;b;  ;", "xabc yzabc abc", "qabc abc", "abcabc zabc abcd",
            "aabc bc abc", "ABC aBc \u00c9T\u00c9 \u00e9t\u00e9", "abcx\nabc", "abc"])

# heads without a bounded width, or ^ of the whole string: the general case
for p in [r".*abc", r"\w+;", r"^abc", r"(?m)^abc", r"\Aabc", r"(a|b*)c", r"(?:a|b+)c"]:
    run(p, ["xxabc\nabc", "ab;cd;", "abc abc", "bbbc ac"])

# a literal straddling endpos, and starts before pos that the head would need
rx = re.compile(r"(?:x|yz)abc")
t = "yzabc yzab"
print([describe(rx.search(t, p, e)) for p in range(0, 4) for e in [4, 5, 9, 10]])
