# del of a parameter unbinds it, as del of any other local does


def f(x: str, c: bool) -> None:
    if c:
        del x
    print(x)


def g(x: str | None) -> None:
    if x is not None:
        del x
    print(x)


f("a", False)
g(None)
g("b")
