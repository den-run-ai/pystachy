# Single-character assertions and first-character rejection must retain ordinary re semantics.
import re


def show(p, text: str, pos: int, endpos: int) -> None:
    m = p.search(text, pos, endpos)
    if m is None:
        print("None")
    else:
        print(m.span(), repr(m.group()), [repr(m.group(i)) for i in range(1, p.groups + 1)], m.lastindex)


for pattern in [r"(?=a)a", r"(?!a).", r"(?<=a).", r"(?<!a).",
                r"(?=[ab]).", r"(?![ab]).", r"(?<=[ab]).", r"(?<![ab]).",
                r"(?=\w).", r"(?!\w).", r"(?<=\w).", r"(?<!\w).",
                r"(?=.).", r"(?!.).", r"(?<=.).", r"(?<!.).",
                r"(?s)(?=.).", r"(?s)(?<!.).", r"(?i)(?=a).", r"(?i)(?<![ab]).",
                r"(?a)(?i)(?=a).", r"(?a)(?i)(?<![ab]).",
                r"(?=[^a]).", r"(?<![^a]).", r"(?=[ab]{2}).", r"(?<!a{2}).",
                r"(?=a(b))a", r"(?!a(b))a", r"(?<=a(b))c", r"(?<!a(b))c",
                r"(?=a*)b", r"(?!a*)b", r"(?=a+)a", r"(?!a+)b",
                r"(?=a+?)a", r"(?=a++)a", r"(?=a{0}b)b", r"(?=a{0}b*)b",
                r"(?=a|b).", r"(?=a?b).", r"(?=a$).", r"(?=a\b).",
                r"(?:(?=a)a|(?!a)b)+", r"(?:(?=a(b))a|b)+",
                r"(?<=[\w!\"'&.,?])(?=-{2,}\w)"]:
    print(pattern)
    p = re.compile(pattern)
    for text in ["", "a", "b", "A", "\n", " abca!a--z a-b", "aaab"]:
        show(p, text, 0, len(text))
        show(p, text, 1, len(text))
        show(p, text, 0, max(0, len(text) - 1))

# Unicode folding/classes, a lookbehind before pos, and truncation at endpos.
# Printed text rather than code-point spans keeps this differential case valid on UTF-8 strs.
for pattern in [r"(?i)(?=k).", r"(?i)(?<!k).", r"(?i)(?=[a-z]).", r"(?i)(?<![a-z]).",
                r"(?=\w).", r"(?a)(?=\w).", r"(?<=\w).", r"(?a)(?<=\w)."]:
    print(pattern)
    p = re.compile(pattern)
    for text in ["éa", "Ka", "ſa", "ıa", "σa", "𝒜a"]:
        for m in p.finditer(text):
            print(repr(m.group()), m.lastindex)
