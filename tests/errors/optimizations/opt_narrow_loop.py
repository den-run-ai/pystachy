# error: argument 1 of show() may be None (str | None); test it with 'is not None' first
def show(s: str) -> None:
    print(s)


def report(x: str | None, ys: list[str | None]) -> None:
    if x is not None:
        for y in ys:
            show(x)  # x may be None on the loop's second pass
            x = y


report("a", ["b", None])
