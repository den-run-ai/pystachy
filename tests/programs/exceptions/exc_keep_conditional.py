# Where __init__ may end without calling super().__init__() (a return before it, or the call in
# an if), the object keeps the arguments it was made with: str(e) shows their tuple.
class Maybe(ValueError):
    def __init__(self, a: int, b: int) -> None:
        self.a = a
        if a == 0:
            return
        super().__init__(a * b)


class Cond(ValueError):
    def __init__(self, a: int, b: int) -> None:
        if a > 0:
            super().__init__(a)


class Looped(ValueError):
    def __init__(self, a: int, b: int) -> None:
        for _ in range(a):
            super().__init__(b)


print(str(Maybe(0, 5)), repr(Maybe(0, 5)), str(Maybe(2, 5)), repr(Maybe(2, 5)))
print(str(Cond(1, 2)), repr(Cond(-1, 2)), str(Cond(-1, 2)))
print(str(Looped(0, 7)), str(Looped(2, 7)), repr(Looped(0, 7)))
