# keys that collide in the runtime's hash table: they must keep their values, their insertion
# order and their deletions through lookups, rebuilds and copies

# the runtime's hashes of these share their low 16 bits, so they start at the same slot of every
# table up to 2**16 slots and part only as the probe sequence mixes in the higher bits
SAME = [8325434945604653754, -8555982781702063117, -2361855011284423965, -8585158661107011472,
        7556889393377358975, -7194060334836440460, 6224643513991142028, 7318753877597238267,
        2415524748319890168, 2208418779665543153, -513459404413015021, 7890037892773340458,
        253436173304025021, 9072999726065184528, -8634785171935344120, 5892873317257306375,
        3660650541115925848, 8132327399060254830, 2495477513363830055, -2938543440313966440,
        -2527664044776066465, 1353838622833337194, 2723412083218717700, -9136042476777479891]
# the runtime hashes 0 and this key alike
TWIN = -7575587744497664804


def check(d: dict[int, int], ks: list[int]) -> int:
    # values of ks in d (-1 if absent), as a checksum, and the dict's items in order
    s = 0
    for k in ks:
        s = (s * 31 + d.get(k, -1)) % 1000000007
    for k, v in d.items():
        s = (s * 31 + v + k % 1000003) % 1000000007
    return s


d: dict[int, int] = {}
for i in range(len(SAME)):
    d[SAME[i]] = i
print(len(d), [d[k] for k in SAME[:6]], check(d, SAME))
for i in range(0, len(SAME), 2):
    del d[SAME[i]]
print(len(d), SAME[0] in d, SAME[1] in d, d.get(SAME[2], -1), check(d, SAME))
for i in range(0, len(SAME), 4):
    d[SAME[i]] = 100 + i
print(len(d), list(d.values()), check(d, SAME))
for i in range(1000):
    d[i << 46] = i
print(len(d), check(d, SAME), d[SAME[1]], d[999 << 46], dict(d) == d, d.copy() == d)
c = dict(d)
for i in range(1, len(SAME), 2):
    print(c.pop(SAME[i]), end=" ")
print(len(c), check(c, SAME))

t = {0: "zero", TWIN: "twin"}
print(t, t[0], t[TWIN], 0 in t, TWIN in t)
del t[0]
print(t, 0 in t, TWIN in t, t.get(0, "none"))
t[0] = "back"
t.setdefault(TWIN, "unused")
print(t, list(t.keys()))
e = {9223372036854775807: 1, -9223372036854775807 - 1: 2, -1: 3, 1: 4, 1 << 62: 5, -(1 << 62): 6}
print(e, e[-1], e[-9223372036854775807 - 1])

# keys that differ only in their high bits, at a size where they used to form one cluster
h: dict[int, int] = {}
for i in range(30000):
    h[i << 46] = i
for i in range(0, 30000, 3):
    del h[i << 46]
s = 0
for i in range(30000):
    s += h.get(i << 46, 0)
print(len(h), s, (29999 << 46) in h, (30000 << 46) in h, list(h.values())[:5], list(h.keys())[-1])

# str keys that differ only in letter case, or at one end of a long common part
w: dict[str, int] = {}
for i in range(256):
    w["".join([chr(97 + j - 32 * (i >> j & 1)) for j in range(8)])] = i
print(len(w), w["abcdefgh"], w["ABCDEFGH"], w["aBcDeFgH"], "abcdefgH" in w, "abcdefghi" in w)
ws = list(w.keys())
for i in range(0, len(ws), 2):
    del w[ws[i]]
print(len(w), list(w.items())[:3], w.get("abcdefgh", -1), w["Abcdefgh"])
p: dict[str, int] = {}
for i in range(2000):
    p["x" * 100 + str(i)] = i
    p[str(i) + "y" * 100] = -i
print(len(p), p["x" * 100 + "1999"], p["7" + "y" * 100], ("x" * 100 + "2000") in p, ("y" * 100) in p)
