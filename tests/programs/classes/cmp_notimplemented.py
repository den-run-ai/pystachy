class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, V):
            return NotImplemented
        return self.n == other.n

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, V):
            return NotImplemented
        return self.n < other.n


xs = [V(2), V(1), V(3)]
print(xs[0] < xs[1], xs[1] < xs[0], xs[0] == xs[1], xs[0] == xs[0], xs[0] != xs[1])
print([v.n for v in sorted(xs)])
print(V(1) == 3, V(1) != 3, 3 == V(1), V(1) == "a", V(1) == None, None == V(1))
a = V(1)
b = V(2)
print(a < b, b < a, max(a, b).n, min(xs).n)
print(a > b, b > a)
for other in [3]:
    try:
        print(a < other)
    except TypeError as e:
        print("TypeError", e)


def f(p: V, q: V) -> bool:
    return p < q


print(f(a, b), f(b, a))
print(V(2) in xs, V(9) in xs, xs.index(V(3)), xs.count(V(1)))
