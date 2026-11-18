# A sentinel parameter that a nested function assigns (nonlocal) may hold another object() where
# its test runs, which then reads it at run time, as CPython's does; a closure that only reads it
# tests what the call gave
S = object()


def f(x: int = S, flag: bool = False) -> bool:
    def replace() -> None:
        nonlocal x
        x = object()

    if flag:
        replace()
    return True if x is S else False


def g(x: list[int] = S) -> bool:
    def later() -> bool:
        return x is S

    return later()


print(f(), f(flag=True), g(), g([3]))
