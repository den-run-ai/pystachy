# == between objects of exception classes with a base in common calls that base's __eq__.
class E(Exception):
    def __init__(self, n: int) -> None:
        super().__init__(n)
        self.n = n

    def __eq__(self, other: "E") -> bool:
        return other.n == self.n


class F(E):
    pass


class G(E):
    pass


print(E(1) == F(1), F(1) == E(2), F(3) != G(3), F(1) == G(2), E(1) == E(1))


class H(Exception):
    pass


class I(H):
    pass


h = H("h")
i = I("i")
print(h == i, i == i, h != i)
