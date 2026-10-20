class A:
    def __init__(self, x: int):
        self.x = x

    def __gt__(self, other: "A") -> bool:
        return self.x > other.x


class P:
    def __init__(self, x: int):
        self.x = x

    def __lt__(self, o: "P") -> bool:
        print("lt", self.x, o.x)
        return self.x < o.x


print([a.x for a in sorted([A(2), A(1)])])
print(sorted([P(1), P(2)])[0].x)
print(max([P(1), P(2)]).x)
print(min(P(3), P(1)).x, max(P(3), P(1)).x)
print(A(1) < A(2), A(3) > A(2))
