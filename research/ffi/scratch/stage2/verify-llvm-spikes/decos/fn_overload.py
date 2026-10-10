from typing import overload
@overload
def f(x: int) -> int: ...
@overload
def f(x: str) -> str: ...
def f(x):
    return x
print(f(1), f("a"))
