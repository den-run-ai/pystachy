# lib/re skips a branch's alternative, and a search's position, where a character repeated at least
# once at its start cannot be (not _sre's: tests the character before the nested match, the same
# result): against CPython's re, alternatives and patterns that begin with greedy, lazy and
# possessive repeats of a literal or a class, behind groups or not, with a minimum of 0 (not
# skipped), IGNORECASE classes (not skipped), pos and endpos, counts and textwrap's word splits
import re

PATTERNS = [r"([ \t]+)", r"[ \t]+", r"(a+)b", r"((x+?)y)", r"(?:[0-9]++)\.", r"a*b", r"(?i)([a-c]+)d",
            r"[ \t]+|[^ \t]+?(?=[ \t]|$)", r"(?:a+|b+|-)c", r"(?:a+?|[xy]{2,})z", r"(?:\d+|(?=x)x)!",
            r"([^ ]++)(?: |$)", r"(?:ab+|a)", r"(?:[a-c]{2}|[b-d]+)e"]
TEXTS = ["", "a", " ", "  a b\tc  ", "aab ab b", "xxy xy y", "12. 3.4 .5", "abcd ABCD aCbd",
         "aac bbc -c ac", "aaz xyz xz z", "12! x! !", "one two  three", "abbb abab a", "abe bce cde dde"]
for p in PATTERNS:
    rx = re.compile(p)
    print(repr(p))
    for t in TEXTS:
        spans: list[str] = []
        for m in rx.finditer(t):
            g = repr(m.group(rx.groups)) if rx.groups else ""
            spans.append(f"{m.start()}:{m.end()}{g}")
        print("  ", repr(t), " ".join(spans), repr(rx.sub("|", t, 3)), rx.split(t)[:6] if rx.groups < 2 else [])
    t = TEXTS[3]
    bounds: list[str] = []
    for pos in range(len(t) + 1):
        for endpos in [len(t), pos + 2]:
            m = rx.search(t, pos, endpos)
            bounds.append("-" if m is None else f"{m.start()}:{m.end()}")
    print("   pos/endpos", " ".join(bounds))

# textwrap's word splits (break_on_hyphens=False and True)
simple = re.compile(r"([\t\n\x0b\x0c\r ]+)")
wordsep = re.compile(r"""
    ( # any whitespace
      [\t\n\x0b\x0c\r ]+
    | # em-dash between words
      (?<=[\w!"'&.,?]) -{2,} (?=\w)
    | # word, possibly hyphenated
      [^\t\n\x0b\x0c\r ]+? (?:
        # hyphenated word
          -(?: (?<=[^\d\W]{2}-) | (?<=[^\d\W]-[^\d\W]-))
          (?= [^\d\W] -? [^\d\W])
        | # end of word
          (?=[\t\n\x0b\x0c\r ]|\Z)
        | # em-dash
          (?<=[\w!"'&.,?]) (?=-{2,}\w)
        )
    )""", re.VERBOSE)
for t in ["Hello there -- how are you?", "a well-known  self-evident e-mail\tre-entry", "  leading and trailing  ",
          "x--y z---w -- ab--", "caf\xe9 na\xefve-r\xe9sum\xe9 ☃☃"]:
    print(simple.split(t), wordsep.split(t))
