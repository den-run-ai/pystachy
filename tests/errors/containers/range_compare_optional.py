# error: comparing a range with int | None is not supported
# (a range never equals an int, but None may be the range: a range | None that is None)
def f(x: int | None) -> bool:
    return range(1) == x


print(f(None))
