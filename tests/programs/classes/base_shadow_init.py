class B:
    def __init__(self, x: int) -> None:
        self.x = x


def argument(x: int) -> int:
    print("argument", x)
    return x


class E(B):
    def __init__(self, B: int) -> None:
        self.x = B
        B.__init__(self, argument(99), ignored=argument(100))


class Local(B):
    def __init__(self, x: int) -> None:
        B = x
        self.x = x
        B.__init__(self, 99)


class Comp(B):
    def __init__(self, x: int) -> None:
        self.x = x
        print([B.__init__(self, 99) for B in [1, 2]])
        B.__init__(self, x + 1)


print(E(5).x, Local(6).x, Comp(7).x)
