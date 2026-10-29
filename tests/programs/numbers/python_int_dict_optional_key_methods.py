# pystachy: python-int
# get() and pop() of dicts of int keys by an int | None key: past 64 bits, -2**63, one that fits or
# None (which is in no dict); of int values (which may be past 64 bits too), str, float (whose
# get(k) and pop(k, None) give a box) and list values, found or missing, with their defaults, and
# KeyError (None's too) where pop() has none.
big = 2 ** 64
m63 = -2 ** 63


def pick(flag: int) -> int | None:
    if flag == 0:
        return None
    if flag == 1:
        return m63
    return big * flag if flag > 2 else flag


def lookups(counts: dict[int, int], names: dict[int, str], k: int | None) -> None:
    print(counts.get(k), counts.get(k, -1), names.get(k), names.get(k, "?"))


counts: dict[int, int] = {big * 3: big * 3, m63: 7, 2: big}
names: dict[int, str] = {big * 3: "b", m63: "m", 2: "two"}
ratios: dict[int, float] = {big * 3: 0.5}
groups: dict[int, list[int]] = {big * 3: [1]}
for flag in [3, 1, 2, 0, 4]:
    k = pick(flag)
    lookups(counts, names, k)
    print(ratios.get(k), ratios.get(k, 2.0), groups.get(k, [])[:1])
print(counts.pop(pick(4), 0), counts.pop(pick(0), big), names.pop(pick(0), "none"), counts.pop(pick(4), None))
print(counts.pop(pick(3), None), ratios.pop(pick(3), None), ratios.pop(pick(0), None), ratios)
print(counts.pop(pick(1)), names.pop(pick(1)), names.pop(pick(3)), counts.pop(pick(2)), counts, names)
for flag in [0, 5]:
    k = pick(flag)
    try:
        counts.pop(k)
    except KeyError as e:
        print("KeyError:", e)
    try:
        names.pop(k)
    except KeyError as e:
        print("KeyError:", e)
