# a | b and dict(pairs) of dicts whose keys are objects: CPython's calls of __hash__ (once for each
# pair; a | b takes the hashes the dicts keep) and __eq__ (for each stored key of the same hash
# that the probes meet), which may change what the caller sees


class K:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: "K") -> bool:
        counts[1] += 1
        return self.n == other.n

    def __hash__(self) -> int:
        counts[0] += 1
        return self.n % 2

    def __repr__(self) -> str:
        return f"K({self.n})"


class Node:
    def __init__(self, n: int) -> None:
        self.n = n

    def __repr__(self) -> str:
        return f"Node({self.n})"


counts = [0, 0]


def union(a: dict[K, int], b: dict[K, int], seen: list[int]) -> int:
    before = seen[1]
    c = a | b
    print(c)
    return seen[1] - before


def pairs(ps: list[tuple[K, int]], seen: list[int]) -> int:
    before = seen[0]
    d = dict(ps)
    print(d)
    return seen[0] - before


a = {K(1): 1, K(2): 2}
b = {K(3): 3, K(4): 4, K(1): 5}
counts[0] = counts[1] = 0
print("eq calls in a | b:", union(a, b, counts), counts)
counts[0] = counts[1] = 0
print("hash calls in dict(pairs):", pairs([(K(5), 5), (K(6), 6), (K(7), 7), (K(5), 8)], counts), counts)
c = a
c |= {K(9): 9}
print(c, a, counts)
nodes = [Node(i) for i in range(4)]
m = {nodes[0]: 0, nodes[1]: 1} | {nodes[1]: 10, nodes[2]: 2}
print(len(m), m[nodes[1]], nodes[3] in m)
p = dict([(nodes[3], 3), (nodes[0], 0), (nodes[3], 33)])
print(len(p), p[nodes[3]], list(p.values()))
