import mymod


def top(n: int) -> int:
    return mymod.helper(n)


class P:
    def __init__(self, x: int) -> None:
        self.x = x

    def get(self) -> int:
        return self.x


def mk(x: int) -> P:
    return P(x)
