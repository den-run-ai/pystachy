# lib/re's search of a pattern that begins with ^ of MULTILINE (after groups' marks), which enters
# the matcher only where a line begins, against CPython's re: search() with pos and endpos (a pos
# inside a line is no line's start), findall(), finditer(), sub() and subn() (empty matches, a
# replacement function that runs another such search), split(), and the patterns of textwrap's
# dedent()
import re

PATTERNS = [r"^", r"^$", r"^[ \t]+$", r"(^[ \t]*)(?:[^ \t\n])", r"^ab", r"(^)(x)?", r"^(?=a)", r"((^a))",
            r"^\n", r"^.*$", r"^(?:a|b)", r"^\w+", r"^(?<=\n)x", r"^a*", r"^(a)?$", r"(?:^)b", r"^   "]
TEXTS = ["", "\n", "\n\n", "a\nb", "a\n", "\na", "ab\nab\n", "  \n\t\nx  \n   y\n", "a\r\nb\r\n",
         "ab" * 20 + "\nxab\n\n  ab", "   a\n    b\n\n     c\n"]
for p in PATTERNS:
    rx = re.compile(p, re.MULTILINE)
    print(repr(p))
    for t in TEXTS:
        spans = [(m.span(), m.span(rx.groups)) for m in rx.finditer(t)]
        # (findall() of 2 groups or more, and a split() that a group would give a None, raise
        # NotImplementedError in lib/re: lib/README.md)
        found = rx.findall(t)[:6] if rx.groups < 2 else []
        parts = rx.split(t)[:5] if rx.groups == 0 else []
        print("  ", repr(t), spans, found, repr(rx.sub("<>", t)), rx.subn("|", t, 2)[1], parts)
    t = TEXTS[7]
    bounds: list[str] = []
    for pos in range(len(t) + 1):
        for endpos in [len(t), len(t) - 1, pos + 3, pos]:
            m = rx.search(t, pos, endpos)
            bounds.append("-" if m is None else f"{m.start()}:{m.end()}")
    print("   pos/endpos", " ".join(bounds))


# a replacement function that runs another multiline search: each search keeps its own state
inner = re.compile(r"^\s*(\w)", re.MULTILINE)


def initials(m: re.Match) -> str:
    return "[" + "".join(inner.findall(m.group(0) or "")) + "]"


outer = re.compile(r"^(?:\w+ ?)+$", re.MULTILINE)
print(outer.sub(initials, "alpha beta gamma\ndelta\n  \nepsilon zeta\n"))

# dedent()'s regular expressions, on blocks of lines
blocks = ["    a\n    b\n", "  x\n\n    y\n  \t\n", "\tone\n\t\ttwo\n", "no indent\n  some\n", "    \n    \n", "    last"]
only = re.compile(r"^[ \t]+$", re.MULTILINE)
leading = re.compile(r"(^[ \t]*)(?:[^ \t\n])", re.MULTILINE)
for b in blocks:
    text = only.sub("", b)
    print(repr(text), leading.findall(text), repr(re.sub(r"(?m)^  ", "", text)))
