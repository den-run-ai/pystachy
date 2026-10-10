import typing
@typing.overload
def f(x: int) -> int: ...
def f(x: int) -> int:
    return x
print(f(1))
