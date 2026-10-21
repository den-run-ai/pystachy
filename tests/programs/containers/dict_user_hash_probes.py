# Keys of equal hashes: a lookup runs __eq__ for each key of its hash that its probes meet, in
# CPython's order, and again where they visit a slot again, as CPython's probe sequence does: it
# starts from the hash's low bits and mixes its high bits in at each step, so a large hash's
# first steps can come back to a slot (a hash of 0, and of -1, which is -2 as in CPython,
# included); also after deletions, a resize and in sets
log: list[str] = []


class Key:
    def __init__(self, name: str, h: int) -> None:
        self.name = name
        self.h = h

    def __eq__(self, other: "Key") -> bool:
        log.append(f"{self.name}={other.name}")
        return self.name == other.name

    def __hash__(self) -> int:
        return self.h

    def __repr__(self) -> str:
        return self.name


def lookups(h: int, n: int) -> None:
    # n keys of hash h, one of them deleted and one more added, then an absent key and a present
    # one looked up: the __eq__ calls each lookup made
    d: dict[Key, int] = {}
    for i in range(n):
        d[Key(f"a{i}", h)] = i
    del d[Key("a1", h)]
    d[Key("b", h)] = n
    log.clear()
    print(Key("x", h) in d, log)
    log.clear()
    print(d.get(Key(f"a{n - 1}", h)), log)
    log.clear()
    s = set(d)
    print(Key("x", h) in s, log, len(s))


for h in [0, 1, -1, 7, 1 << 40, (1 << 62) + 5, -(1 << 62) - (1 << 62), hash((1, 2)), hash((3, "x".isalpha()))]:
    print(hash(Key("k", h)) == h or h == -1, hash(Key("k", h)))
    lookups(h, 3)
    lookups(h, 6)

# keys of two hashes that share their low bits: the probes of one meet the other's keys too, but
# __eq__ runs only for keys of the same hash
d: dict[Key, int] = {}
for i in range(5):
    d[Key(f"p{i}", 3 + (i % 2) * (1 << 50))] = i
log.clear()
print(Key("q", 3) in d, Key("r", 3 + (1 << 50)) in d, log)
# a resize keeps the order, and lookups find each key with no __eq__ of another
big: dict[Key, int] = {}
keys = [Key(f"k{i}", (i % 3) << 33) for i in range(40)]
for i, k in enumerate(keys):
    big[k] = i
log.clear()
print(sum(big[k] for k in keys), len(log), list(big)[:5])
