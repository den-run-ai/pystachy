# error: cannot infer the type of 'out', an empty list so far: annotate it (out: list[T] = [])
class listing:
    def __init__(self, n: int) -> None:
        self.n = n


def show(x: listing) -> None:
    print(x.n)


def f() -> None:
    out = []
    show(out)


f()
