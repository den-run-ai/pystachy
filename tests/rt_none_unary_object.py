class V:
    def __init__(self, n: int) -> None:
        self.n = n

    def __neg__(self) -> "V":
        return V(-self.n)


def pick(k: int) -> V | None:
    return V(k) if k > 0 else None


print((-pick(2)).n)
v = pick(0)
print(-v)
