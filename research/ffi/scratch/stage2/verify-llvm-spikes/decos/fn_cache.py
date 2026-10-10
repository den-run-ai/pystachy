import functools
@functools.cache
def f(x: int) -> int:
    return x
print(f(1))
