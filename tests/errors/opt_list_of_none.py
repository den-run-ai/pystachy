# error: cannot infer the type of a list of None; add a type annotation
def f(n: int) -> None:
    xs = [None] * n  # (xs: list[str | None] = [None] * n works)
    xs[0] = "a"
    print(xs)


f(3)
