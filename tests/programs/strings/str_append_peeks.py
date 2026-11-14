# A str local that appends build stays the local's own through the methods that only read it
# (calls.py's STR_PEEKS: startswith, endswith, find, count, the is*() tests and their kin), as it
# does through len(): the next append still writes in place, so a loop that appends and then tests
# what it built is linear. What the methods return must be what CPython's return for each str the
# loop builds, also past 8,200 bytes (a large object) and for text that is not ASCII, whose
# code-point counts and offsets an append changes. Every read that keeps the str (a list, a dict's
# key, another variable, an argument that reads the local) still gets a str no later append changes.


def block_comment(text: str) -> str:
    # as json_repair's skip_comment() builds a block comment
    comment = "/*"
    index = 2
    while index < len(text):
        comment += text[index]
        index += 1
        if comment.endswith("*/"):
            break
    return comment


def tests(n: int) -> list[int]:
    s = ""
    hits = [0, 0, 0, 0, 0, 0, 0]
    for i in range(n):
        s += chr(97 + i % 7) + str(i % 10)
        if s.startswith("a0b1"):
            hits[0] += 1
        if s.endswith(("d3", "g6", "zz")):
            hits[1] += 1
        hits[2] += s.find("c9")
        hits[3] += s.rfind("a")
        hits[4] += s.count("e4")
        hits[5] += s.index("a0") + s.rindex("0")
        if s.isalnum() and s.isascii() and not s.isdigit():
            hits[6] += 1
    return hits + [len(s)]


def classes() -> list[bool]:
    out: list[bool] = []
    # (no cased letter that is not ASCII: the case tests are ASCII-only, a documented deviation, #120)
    for piece in ["1", "2", "x", "Y", " ", "\u0663", "\u00b2", "\u4e2d"]:
        s = ""
        for _ in range(3):
            s += piece
            out.extend([s.isdigit(), s.isalpha(), s.isalnum(), s.isspace(), s.isupper(), s.islower(), s.istitle(),
                        s.isascii(), s.isdecimal(), s.isnumeric()])
    return out


def unicode_offsets(n: int) -> list[int]:
    # offsets and counts are in code points: appends of non-ASCII text between the reads
    s = ""
    total = [0, 0, 0, 0, 0]
    pieces = ["na\u00efve ", "\u65e5\u672c\u8a9e", "abc", "\U0001f600!", "\u00e9"]
    for i in range(n):
        s += pieces[i % 5]
        total[0] += s.find("\u672c", i // 2)
        total[1] += s.rfind("\u00e9")
        total[2] += s.count("\u00ef", 3, len(s) - 1)
        total[3] += s.find("!", 0, i)
        if s.endswith("\u00e9") or s.startswith("na\u00ef", 0, 3):
            total[4] += len(s)
    return total + [len(s), ord(s[-1])]


def missing(n: int) -> list[int]:
    s = ""
    errors = 0
    found = 0
    for i in range(n):
        s += "ab"
        try:
            found += s.index("ba", i)
        except ValueError:
            errors += 1
    return [errors, found, len(s)]


def kept(n: int) -> list[str]:
    # reads that keep the str, each after a read that does not
    s = ""
    held: list[str] = []
    seen: dict[str, int] = {}
    alias = ""
    for i in range(n):
        s += "k%d" % i
        if s.endswith(str(i)):
            held.append(s)
        if s.startswith("k"):
            seen[s] = i
        if s.count("k") == 3:
            alias = s
    s += "!"
    return held + [alias, s, str(seen[held[2]]), str(len(seen)), str(sorted(seen.values()))]


def own_arguments(n: int) -> list[int]:
    # the argument reads the local itself, or binds another name to what the local held
    s = ""
    out: list[int] = []
    for i in range(n):
        s += "xy"
        out.append(s.count(s[-1]) + s.find(s[1:]))
        if s.endswith(s):
            out.append(len(s))
        found = s.count((t := s + "x"))
        out.append(found + len(t))
        s += "z"
        out.append(len(t) - len(s))
    return out


def large(n: int) -> list[int]:
    s = ""
    ends = 0
    for i in range(n):
        s += "abcdefgh"[i % 8]
        if s.endswith("h"):
            ends += 1
        if i % 1000 == 999:
            ends += s.count("abcdefgh") + s.rfind("gh")
    return [len(s), ends, s.count("ha")]


def main() -> None:
    n = 12000  # (past 8,200 bytes, where a str is a large object)
    for text in ["/**/x", "/*a*/b", "/*/ */", "/* open", "/*" + "y" * n + "*/ tail", "/*" + "\u00e9*" * 700 + "/ "]:
        c = block_comment(text)
        print(len(c), c[:6], c[-6:])
    print(tests(1), tests(2), tests(40), tests(3000))
    print("".join(["1" if b else "0" for b in classes()]))
    print(unicode_offsets(1), unicode_offsets(7), unicode_offsets(600))
    print(missing(1), missing(50))
    print(kept(4))
    print(own_arguments(3))
    print(large(n))


main()
