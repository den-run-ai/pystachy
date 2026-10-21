# error: g() takes 1 positional argument but 2 positional arguments (and 1 keyword-only argument) were given
def g(a: int, *, b: int) -> int:
    return a + b


print(g(1, 2, b=3))
