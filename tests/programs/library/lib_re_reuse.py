# lib/re's matcher keeps its contexts for reuse, the state's for all its matches: a context taken
# again must start as a new one, a match nested in a repeat's count must take the contexts above
# its caller's, and a regular expression run inside a replacement function keeps its own.
# Against CPython's re: matches of
# varied depth one after another, with groups, backreferences, conditionals, lookarounds, lazy,
# atomic and possessive repeats.
import re

PATTERNS = [
    r"(?i)(?:[a-z]+|[0-9]+)(?=[A-Z]*!)",
    r"(?i)((?:ab|cd)+?)([^x!]+?)\1",
    r"(?i)(?<=[a-z]{2})[B-D]+?(?![e])",
    r"((?:(a)|b)+?)c",
    r"(a)?(?(1)b|c)+",
    r"(?>a+|b+)(?=c)",
    r"(?i)[a-c]++d",
    r"(?:(\w)(?:\1|-))+",
    r"(?i)(?:x|(?=[a-d]{2})(?:[a-z](?<![e-z])){1,3})+?!",
    r"(?:a(?:b(?:c(?:d(?:e)?)?)?)?)+",
    r"(?i)(?:(?:[a-z]+)?\d)+",
]
TEXTS = ["ab cd ABCD! abab12! 123! xx", "abxcdcd!abab-ab abcabcc bbbc ac", "aab c abcd aaaabbbbc ccc!",
         "a-a-bb-cc!b x!abcde abcdeabcd", "ABCDd aBcD!d cccd ab12ab3 AA1", "a" * 30 + "c" + "ab" * 15 + "!"]
for p in PATTERNS:
    rx = re.compile(p)
    print(repr(p), rx.groups)
    for t in TEXTS:
        found: list[str] = []
        for m in rx.finditer(t):
            gs = [repr(m.group(i)) for i in range(1, rx.groups + 1)]
            found.append(f"{m.start()}:{m.end()}" + ("(" + ",".join(gs) + ")" if gs else ""))
        print("  ", " ".join(found))


# a replacement function that runs other regular expressions at each match, a nested sub() among
# them: each keeps its own state, contexts and marks
vowels = re.compile(r"(?i)[aeiou]")
word = re.compile(r"(?i)\b([a-z])([a-z]*)\b")


def swap(m: re.Match) -> str:
    rest = m.group(2) or ""
    return vowels.sub(lambda v: (v.group(0) or "").upper(), rest) + (m.group(1) or "") + str(len(list(word.finditer(rest))))


print(word.sub(swap, "the quick brown fox, jumps over the lazy dog"))
print(re.sub(r"(\w+)-(\w+)", lambda m: re.sub(r"(?i)[a-c]+", "<>", (m.group(2) or "") + (m.group(1) or "")), "ab-cd caba-bcd x-y"))
