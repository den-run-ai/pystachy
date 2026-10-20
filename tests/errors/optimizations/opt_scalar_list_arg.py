# error: expected list[float | None], got list[float]
def f(xs: list[float | None]) -> None:
    print(xs)


ys: list[float] = [1.0]
f(ys)
