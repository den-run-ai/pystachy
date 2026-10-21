# error: f() got some positional-only arguments passed as keyword arguments: 'a'
def f(a: int, /) -> int:
    return a * 2


print(f(a=5))
