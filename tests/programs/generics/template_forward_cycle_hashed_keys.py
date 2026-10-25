# A function that returns a call cycle's dict unchanged (b: return a(n)) stores its key layout in
# it as each call returns (#595), and once the cycle recurses, that dict already holds keys. Keys
# hashed by their class have CPython's probe table, which the store must keep: the lookups and
# insertions after it probed twice that table's slots, missing K(1) and K(2)
class K:
    def __init__(self, n: int):
        self.n = n

    def __hash__(self) -> int:
        return self.n * 8 + 1  # (bit 3 differs: an 8-slot table's mask drops it)

    def __eq__(self, other: "K") -> bool:
        return self.n == other.n


G: dict[K, int] = {K(0): 0}


def emptyd(n):
    out = {}
    return out


def a(n):
    global G
    if n <= 0:
        return emptyd(n)
    r: dict[K, int] = b(n - 1)
    r[K(n)] = n
    G = r
    return r


def b(n):
    try:
        return a(n)
    finally:
        print("in finally", n, [k for k in range(1, 8) if K(k) in G], len(G))


d = a(7)  # (the sixth key grows the table: the stores after it keep the larger one's layout)
print(sorted(d.values()), d[K(3)], K(8) in d, K(9) in d)
