# Case-insensitive class counting must fold before testing the class, preserving scoped ASCII
# vs Unicode rules, count bounds, captures, backtracking and the search's pos/endpos window.
import re


def describe(m: re.Match | None) -> str:
    if m is None:
        return "None"
    groups = [repr(m.group(i)) for i in range(m.re.groups + 1)]
    return str(m.start()) + ":" + str(m.end()) + " " + ",".join(groups)


for mode in ["ai", "ui"]:
    for repeat in ["*", "+", "{2,4}", "{2,4}?", "{2,4}+", "++"]:
        rx = re.compile("(?" + mode + ":([a-z]" + repeat + "))([A-Z]?)!")
        print(mode, repeat)
        for text in ["!", "AbCD!", "AbCDE!", "ſİıK!", "aKB!", "--AbCD!--"]:
            print(describe(rx.search(text)), describe(rx.fullmatch(text)))


for pattern in [
    r"(?i:([^a-c!]+))!",
    r"(?i:([σ]+))!",
    r"(?i:([a\u0100\u0200\u0300\u0400\u0500]+))!",
    r"(?i:([\U00010400-\U00010427]+))!",
    r"(?i:(?<=[a-z])[a-z]{2,4})(?-i:([A-Z]+))!",
    r"(?i:((?:[a-z]{1,3})+?))\1!",
    r"(?i:([a-z]+))(?=!)",
    r"(?i:[a-z]*?)(?=!)",
]:
    rx = re.compile(pattern)
    print(pattern)
    for text in ["aBcABC!", "σςΣ!", "aĀāȀȁ!", "𐐀𐐨𐐁𐐩!", "--AbCD!--"]:
        print(describe(rx.search(text)))


bounded = re.compile(r"(?i:([a-z]+))")
text = "--AſİıKz--"
for pos, end in [(0, 0), (0, 5), (2, 8), (3, 7), (6, 4), (8, 20), (-5, 100)]:
    print(pos, end, describe(bounded.search(text, pos, end)), describe(bounded.fullmatch(text, pos, end)))


for pattern in [r"(?i:([a-z]+))!", r"(?ai:([a-z]+))!", r"(?i:(a+))!", r"(?ai:(a+))!",
                r"(?i:([a-z]{1,3}?))!", r"(?i:([a-z]++))!"]:
    rx = re.compile(pattern)
    for text in ["0" * 20, "0" * 20 + "Aa!", "0" * 20 + "AſİıK!"]:
        print(pattern, describe(rx.search(text)))

# A repeat that can be empty must retain all starting positions, including an empty match
# followed by a nonempty match at the same position (the engine's must_advance rule).
for pattern in [r"(?i:[a-z]*)", r"(?ai:a*?)", r"(?i:[a-z]{0,2})", r"(?i:[a-z]*?)"]:
    for text in ["00", "Aa", "0ſA!"]:
        print(pattern, text, [describe(m) for m in re.finditer(pattern, text)])
