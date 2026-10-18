# str.replace where the occurrences are dense but their search is costly (issue #36's review): a
# needle whose first byte is common where the needle is not, as "CA" in random text over ACG. The
# runtime counts the rest of a dense text only where its failed candidates cost no more than the
# bytes they pass; otherwise it lists them, as for sparse ones, and searches the text once. Either
# way the result is that of replacing the text piece by piece, with fewer occurrences in each
# than the 65,536 the runtime lists before it weighs them. (Few allocations, for the GC-stressed
# suite: no list of every occurrence, as split() would make.)
CAP = 65536


def dna(k: int, reps: int) -> str:
    # random text over the first k letters of ACGT, as an LCG gives it: 8,000 bytes, reps times
    x = 28
    parts: list[str] = []
    for i in range(2000):
        x = (x * 1103515245 + 12345) % 2147483648
        parts.append("ACGT"[x % k] + "ACGT"[(x >> 8) % k] + "ACGT"[(x >> 16) % k] + "ACGT"[(x >> 24) % k])
    return "".join(parts) * reps


def pieces(s: str, old: str, new: str, count: int) -> str:
    # s.replace(old, new, count) by pieces of about 100,000 bytes, each beginning where old occurs
    # (which does not overlap itself, so that each occurrence is one replace finds)
    parts: list[str] = []
    i = 0
    while i < len(s):
        e = s.find(old, i + 100000)
        if e < 0:
            e = len(s)
        piece = s[i:e]
        if count < 0:
            parts.append(piece.replace(old, new))
        else:
            k = min(count, piece.count(old))
            parts.append(piece.replace(old, new, k))
            count -= k
        i = e
    return "".join(parts)


def check(tag: str, s: str, old: str, new: str, counts: list[int]) -> None:
    for count in counts:
        r = s.replace(old, new, count)
        # (lengths and slices only of ASCII text: Pystachy's count bytes)
        print(tag, count, s.count(old), r == pieces(s, old, new, count), r.count(new) if new else 0)
        if r.isascii():
            print(" ", len(r), repr(r[:12]), repr(r[len(r) // 2 : len(r) // 2 + 12]), repr(r[-12:]))


acg = dna(3, 150)
check("acg", acg, "CA", "#", [-1, CAP, CAP + 1, 100000])
check("acg-long", acg, "CA", "<ca>", [-1])
acgt = dna(4, 300)
check("acgt", acgt, "AT", "", [-1, CAP + 1])
check("acgt-3", acgt, "GAC", "x", [-1])
# a dense prefix, then a long run of failed candidates, then the needle once more: a count that
# ends in the prefix needs no count of the run
for old in ["ab", "a" * 15 + "b"]:
    s = old * 70000 + "a" * 300000 + old
    check("prefix" + str(len(old)), s, old, "", [-1, CAP + 1, 70000, 70001])
# dense, costly, then dense again; and failed candidates cheap enough to count past
s = "ab" * 70000 + ("a" * 40 + "ab") * 3000 + "ab" * 100000
check("dense-costly-dense", s, "ab", "Z", [-1, CAP + 1, 140000])
s = ("ab" + "y" * 13 + "ab" + "y" * 12 + "a") * 70000
check("cheap-fails", s, "ab", "-", [-1, CAP + 1, 70001])
# non-ASCII: a 4-byte needle whose first byte begins every character of the text
s = ("éè" * 3 + "ê") * 40000
check("e-accents", s, "éè", "e", [-1, CAP + 1])
