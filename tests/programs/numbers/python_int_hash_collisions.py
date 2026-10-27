# pystachy: python-int
# Dicts of int keys and sets of ints whose keys and elements past 64 bits share CPython's hash with
# each other and with 64-bit ones: k * (2**61 - 1) + 5 hashes as 5 does, and -(k * (2**61 - 1)) - 4
# as -4 and -2**63 do. Their probe chains mix both kinds through insertions, lookups, deletions
# that leave holes, re-insertions, resizes, copies, comparisons and set algebra.
P = 2 ** 61 - 1
up = [k * P + 5 for k in range(1, 121)]
down = [-(k * P) - 4 for k in range(1, 121)]
small = [5, -4, -2 ** 63, 2 ** 63 - 1]
print(len({hash(x) for x in up}), len({hash(x) for x in down + small[:3]}))
d: dict[int, int] = {}
for i in range(120):
    d[up[i]] = i
    d[down[i]] = -i
    if i % 30 == 0:
        for s in small:
            d[s] = i
print(len(d), d[up[119]], d[down[60]], d[5], d[-4], d[-2 ** 63], all([d[up[i]] == i for i in range(120)]))
for i in range(0, 120, 2):
    del d[up[i]]
    d.pop(down[i])
print(len(d), up[0] in d, up[1] in d, down[2] in d, down[3] in d, 5 in d, -4 in d, -2 ** 63 in d)
for i in range(0, 120, 4):
    d[up[i]] = 1000 + i
print(len(d), sum(d.values()), d.get(up[4]), d.get(up[2], -1), d.setdefault(down[0], 7), d.setdefault(down[1], 7))
print(list(d)[:3] == [5, -4, -9223372036854775808], list(d)[-2:] == [up[116], down[0]], sorted(d)[0] == down[119])
e = dict(d)
f = {k: d[k] for k in reversed(list(d))}
print(e == d, f == d, len(f), list(f)[0] == down[0], sorted(e) == sorted(d))
for s in small:
    del e[s]
print(len(e), e == d, e != d, all([k in e for k in up[1::2]]), any([k in e for k in small]))
st = set(up) | set(down) | set(small)
print(len(st), 5 in st, -4 in st, -2 ** 63 in st, up[7] in st, down[7] - P in st)
for i in range(0, 120, 3):
    st.discard(up[i])
    st.remove(down[i])
st -= {5, -4}
print(len(st), sum(1 for x in st if x > 0), -2 ** 63 in st, up[3] in st, up[4] in st, down[4] in st)
st.update(up[:60])
st.symmetric_difference_update(set(down[:60]))
print(len(st), sorted(st)[:2] == [down[119], down[118]], min(st) == down[119], max(st) == up[119])
print(st == set(d) | set(up[:60]), len(st & set(d)), len(st - set(d)), len(set(d) - st))
