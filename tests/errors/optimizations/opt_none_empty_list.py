# error: cannot infer the type of 'x' from None and an empty list; annotate it (x: list[T] | None = None)
def f(c: bool) -> None:
    x = None
    if c:
        x = []
    if x is not None:
        x.append(1)
    print(x)


f(True)
