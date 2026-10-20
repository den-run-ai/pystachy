# [] and {} assigned to a variable without an annotation: the first use that shows what the
# container holds (append, insert, extend, +=, d[k] = v, setdefault, a reassignment) gives the
# variable its type; before that, len() and truth tests may read it.
squares = []
print(len(squares), bool(squares), not squares)
for i in range(5):
    squares.append(i * i)
print(squares)

index = {}
if not index:
    index["a"] = [1]
index.setdefault("b", []).append(2)
print(index, len(index))

counts = {}
for w in "the cat and the hat and the bat".split():
    counts[w] = counts.get(w, 0) + 1
print(counts)

by_len = {}
for w in ["x", "yy", "zz", "w"]:
    by_len[len(w)] = by_len.get(len(w), "") + w
print(by_len, sorted(by_len))


def words(text):
    out = []
    cur = []
    for c in text:
        if c == " ":
            if cur:
                out.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    if cur:
        out.append("".join(cur))
    return out


def merged(a: list[int], b: list[int]) -> list[int]:
    res = []
    res += a
    res.extend(b)
    res.insert(0, -1)
    return res


def grid(n: int) -> list[list[int]]:
    rows = []
    for r in range(n):
        row = []
        for c in range(n):
            row.append(r * n + c)
        rows.append(row)
    return rows


print(words("pack my  box with five"), merged([1, 2], [3]), grid(3))
later = []
later = [1.5, 2.5]
later.append(3.5)
print(later)
empty_ok = {}
print(len(empty_ok))
