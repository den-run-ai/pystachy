# lib/re reads a str whose every byte is a code point (ASCII, or the raw bytes Pystachy's chr()
# makes of 128 to 255) in place, as a bytes, and decodes another into a list of code points: the
# engine is compiled for both. Each pattern runs over subjects of both kinds in turn (sharing its
# class tables and search strategy), with bounds, anchors, lookbehind at the start, case folding,
# backreferences, empty matches and callbacks that match a subject of the other kind.
import re

subjects = ["", "abc abd", "abc\nabd\n", "x" * 40 + "abc", chr(0xE9) + "abc" + chr(0xC9), chr(0x80) + chr(0xFF) + "ab",
            "éabc abd", "abc € abd\n", "\U0001d504abc" + chr(0xE9)]
patterns = [r"ab[cd]", r"(?i)AB(C|D)", r"^ab", r"(?m)^ab", r"d$", r"(?m)d$", r"\babd\b", r"(?<=c)\s", r"\w+", r"[\x80-\xff]+",
            r"(?i)\xe9", r"(.)\1", r"a|b|c", r"x*abc", r"(?s).", r"\Z", r"(?=b)", r"[^a-c\s]+", r"(?i)[\xc0-\xde]"]
for pi in range(len(patterns)):
    rx = re.compile(patterns[pi])
    for si in range(len(subjects)):
        s = subjects[si]
        print(pi, si, [m.span() for m in rx.finditer(s)], rx.subn("-", s)[1], len(rx.split(s)),
              rx.search(s, 1, 5) is not None, rx.match(s) is not None, rx.fullmatch(s) is not None,
              [ascii(x) for x in rx.findall(s)][:3])

inner = re.compile("é|b")
flat_inner = re.compile("b|c")


def callback(m) -> str:
    return str(len(inner.findall("béb" + m.group()))) + str(len(flat_inner.findall("bcb" + m.group()))) + ascii(m.group())


for s in ["abcab", "éabéab", chr(0xE9) + "abab"]:
    print(ascii(re.sub(r"a(b)", callback, s)), ascii(re.subn("b", lambda m: "<" + m.group() + ">", s)))

rx = re.compile("b")
for s in ["abcabc", "ébcabc"]:
    print([(p, e, rx.search(s, p, e) is not None, len(rx.findall(s, p, e))) for p in [-5, 0, 2, 6, 10] for e in [-1, 0, 3, 6, 99]])
for s in ["abc", "ébc", ""]:
    print(ascii(re.sub("x*", "-", s)), ascii(re.split("", s)), ascii(re.findall(r"\b", s)), ascii(re.sub(r"(?<=b)|$", "|", s)))
