# super() in a hierarchy with a method-only secondary base, calling a method that the secondary
# base does not define: CPython's method resolution order (Both, First, Root, Second) finds the
# primary bases' as Pystachy does (super().action() in First is Root's, super().__init__() in
# Both and First the primary's).
class Root:
    def __init__(self, n: int) -> None:
        self.n = n

    def action(self) -> int:
        return self.n


class First(Root):
    def __init__(self, n: int) -> None:
        super().__init__(n * 10)

    def action(self) -> int:
        return super().action() + 1


class Second:
    def read(self) -> int:
        return 2


class Both(First, Second):
    def __init__(self) -> None:
        super().__init__(4)


def use(s: Second) -> int:
    return s.read()


b = Both()
print(b.action(), b.read(), use(b), isinstance(b, Second), isinstance(b, Root))
