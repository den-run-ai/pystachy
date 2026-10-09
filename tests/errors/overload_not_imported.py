# error: overload_not_imported.py:3: error: name 'overload' is not defined (import it from typing)
@overload
def f(x: int) -> int: ...
def f(x: int) -> int:
    return x + 1


print(f(1))
