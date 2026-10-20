# str.replace with many occurrences (issue #36). The runtime lists the first 65,536; where they
# came once every 16 bytes or more often it counts the rest and copies each into a result of its
# final size, else it lists on. Texts are runs of "old + gap" units, dense and sparse, in either
# order, so the expected result is the same runs with new in place of old. Counts stop before, at
# and after the 65,536th occurrence and where the way changes; needles and replacements are empty,
# one byte or several, ASCII or not.
CAP = 65536


def build(runs: list[tuple[str, int]], old: str, new: str, count: int) -> str:
    # the runs of (gap, units) with new for the first count olds (all of them for count < 0)
    parts: list[str] = []
    for gap, k in runs:
        done = k if count < 0 else min(k, count)
        parts.append((new + gap) * done)
        parts.append((old + gap) * (k - done))
        if count >= 0:
            count -= done
    return "".join(parts)


def check(tag: str, runs: list[tuple[str, int]], old: str, new: str, tail: str, counts: list[int]) -> None:
    s = build(runs, old, old, -1) + tail
    for count in counts:
        r = s.replace(old, new, count)
        want = build(runs, old, new, count) + tail
        # (lengths and slices only of ASCII text: Pystachy's count bytes)
        print(tag, count, s.count(old), r.count(new) if new else 0, r.count(old), r == want)
        if r.isascii():
            print(" ", len(r), repr(r[:9]), repr(r[-9:]))


every = [-1, CAP - 1, CAP, CAP + 1, 150000]
# the issue's case, smaller: stars to nothing
check("stars", [("", 200000)], "*", "", "end", every)
check("stars-1", [("", 200000)], "*", "_", "end", [-1, CAP + 1])
check("exactly", [("", CAP)], "*", "_", "", [-1, CAP])
check("comma", [("a", 200000)], ",", ";", "", every)
check("every16", [("y" * 15, 70000)], "*", "", "!", [-1, CAP + 2])
check("every17", [("y" * 16, 70000)], "*", "", "!", [-1, CAP + 2])
check("multi", [("", 100000), ("q", 30000)], "ab", "XYZ", "a", [-1, CAP, 100003])
check("shrink", [("-", 90000)], "<br>", "\n", "<b", [-1, 70000])
# sparse first, then dense: listed past 131,072, then counted; and the other way round
check("sparse-dense", [("y" * 40, 70000), ("", 200000)], "*", "", "", [-1, 131072, 262144, 262145])
check("dense-sparse", [("", 70000), ("y" * 30, 100000)], "*", "--", "", [-1, CAP + 1, 100000])
check("lines", [("the quick brown fox jumps over the lazy", 100000)], "\r\n", "\n", "", [-1, CAP])
# non-ASCII needles, gaps and replacements: whole characters of 2 to 4 bytes
check("e-acute", [("x", 80000), ("", 80000)], "é", "€", "ë", [-1, CAP, 100000])
check("clef", [("", 120000)], "𝄞", "e", "", [-1, CAP + 3])
check("wide-gap", [("日本", 70000)], ",", "", "", [-1])
check("to-wide", [("", 100000)], "-", "→", "", [-1, CAP])
check("same", [("", 100000)], "ab", "ab", "", [-1])

# overlapping candidates: "aa" in a run of a, found left to right without overlaps
s = "a" * 200001
r = s.replace("aa", "b")
print(len(r), r == "b" * 100000 + "a", s.replace("aa", "", CAP + 1) == "a" * (200001 - 2 * (CAP + 1)))
print(s.replace("aaa", "x") == "x" * 66667, s.replace("aaa", "x", 66666) == "x" * 66666 + "aaa")
# an empty needle: new before each character, up to count
t = "ab" * 50000
print(t.replace("", "-", 70000) == "-a-b" * 35000 + "ab" * 15000)
print(len(t.replace("", "")), t.replace("", "", 5) == t)
# a needle that never occurs, and a count of zero
print(t.replace("c", "d") == t, s.replace("a", "b", 0) == s)
# bytes use the same dense replacement path, including NUL and non-UTF-8 data.
raw = b"\x00" * (CAP + 7) + b"\xff"
print(raw.replace(b"\x00", b"\xff", CAP + 1) == b"\xff" * (CAP + 1) + b"\x00" * 6 + b"\xff")
print(raw.replace(b"\x00", b"", CAP + 1) == b"\x00" * 6 + b"\xff")
