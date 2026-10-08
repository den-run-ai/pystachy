# error: f() got a positional-only argument passed as a keyword argument: 'a'
def f(a: int, /) -> int:
    return a * 2


print(f(a=5))
