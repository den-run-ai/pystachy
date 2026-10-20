# An alternative's leading literals and classes are tested before its nested match, which then
# begins after them; a greedy repeat whose tail begins with group marks and a literal skips the
# positions where that literal is not. Cover partial runs, runs that reach the end or endpos,
# alternatives that are prefixes of others, captures, lookbehind, repeated groups and the data
# stack that their backtracking pops, on ASCII and non-ASCII subjects.
import re


def describe(m: re.Match | None) -> str:
    if m is None:
        return "None"
    groups = [repr(m.group(i)) for i in range(m.re.groups + 1)]
    return str(m.start()) + ":" + str(m.end()) + " " + ",".join(groups) + " " + str(m.lastindex)


BRANCHES = [
    r"agggtaaa|tttaccct",
    r"[cgt]gggtaaa|tttaccc[acg]",
    r"ab|abc|abcd",
    r"abcd|abc|ab",
    r"a[bc]d|a[bc]e|a",
    r"(ab)c|(a)bd|(abe)",
    r"x(?:ab|ac)y|xa(d)",
    r"ab+c|ab*d|a",
    r"ab|",
    r"été|é[té]a|[Ѐ-ӿ]x",
    r"(?<=ab|cd)e",
    r"(?<!ab|cd)e",
    r"(?:ab|cd)+e",
    r"(?:(a)b|(a)c)*d",
]
SUBJECTS = ["tttacccttagggtaaacgggtaaatttacccgx", "abcde abd abce ae", "xaby xacy xady xa", "abbbc abd ac",
            "été ééa Аx éta", "abe cde xe e", "ababcde abacd", "aacabd"]
for p in BRANCHES:
    rx = re.compile(p)
    print(p)
    for t in SUBJECTS:
        print(" ", [describe(m) for m in rx.finditer(t)], describe(rx.search(t, 2, 9)))

TAILS = [
    r".*(Python)",
    r".*((P)y)thon",
    r".*(?:(P))ython",
    r"(-+)(P)ython",
    r"[^P]*(P)(y)",
    r"(a).*(b)c",
    r"(?:a.*(b))+c",
    r"(?:.*(x)y)*z",
    r"(?:(a)|b).*(a)",
    r"(?s:.*(\n))",
    r".{2,5}(Py)",
    r".*?(Py)",
    r".*+(Py)",
]
for p in TAILS:
    rx = re.compile(p)
    print(p)
    for t in ["--Python--Python--", "Python", "-P-Py", "abxbc ab bc", "xyxyz xy", "ab ba a", "a\nb\n",
              "éPéPython"]:
        print(" ", describe(rx.search(t)), describe(rx.match(t)), [describe(m) for m in rx.finditer(t)])

# Backtracking into repeated captures restores the marks the data stack holds
for p in [r"(a|b)*c", r"((a)|b)+", r"(?:(a)|(b))+?c", r"((?:a|b)+)(?:c|(d))", r"(a(b)?)+?(c)"]:
    rx = re.compile(p)
    for t in ["ababc", "abab", "abbac", "aabd", "ababcabd", "abaabc"]:
        print(p, t, describe(rx.search(t)), describe(rx.fullmatch(t)))

# ASCII and non-ASCII subjects, also in windows that begin inside them
for t in ["plain ascii text 123", "café été naïve", "\U0001f600 mixed АБ ascii"]:
    rx = re.compile(r"[a-zà-ÿ]+|\d+")
    print([describe(m) for m in rx.finditer(t)], describe(rx.search(t, 3)), describe(rx.search(t, 5, 12)))
