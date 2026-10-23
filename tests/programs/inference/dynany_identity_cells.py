# pystachy: dynamic-any
from typing import Any
from collections.abc import Callable


def same(a: Any, b: Any) -> bool:
    return a is b and id(a) == id(b)


def shared() -> None:
    n = int("1000")

    def read() -> Any:
        return n

    def write() -> Any:
        nonlocal n
        n = int("1000")
        return n

    def keep() -> Any:
        nonlocal n
        n = n
        return n

    # The closure is made before its cell has a box. Both scopes share that box.
    a: Any = read()
    print("shared", same(a, n), same(read(), read()))
    print("self assignment", same(a, keep()))
    # A call may replace a shared cell after the first argument has been read.
    print("replaced", same(n, write()), same(a, n), same(read(), n))
    before: Any = n
    values: list[Any] = [n, n, write()]
    print("delayed", same(values[0], before), same(values[0], values[1]), same(values[1], values[2]))
    # Copying a shared cell to an ordinary local retains the cell's object.
    local = n
    write()
    print("local copy", same(local, values[2]), same(local, n))


def escaped():
    n = int("1234")

    def middle():
        def inner() -> Any:
            return n

        return inner

    return middle()


def floats() -> None:
    x = float("nan")

    def read() -> Any:
        return x

    def write() -> Any:
        nonlocal x
        x = float("nan")
        return x

    a: Any = x
    print("nan", same(read(), a), same(x, write()), same(read(), x), same(a, x))
    x = float("-0.0")
    b: Any = read()
    x = float("-0.0")
    print("negative zero", same(b, x), same(read(), x))
    x = float("0.0")
    print("positive zero", same(b, x), same(read(), x))


def late_loop() -> None:
    readers: list[Callable[[], Any]] = []
    for n in [int("1000"), int("2000")]:
        def read() -> Any:
            return n

        readers.append(read)
    print("loop cell", same(readers[0](), readers[1]()), same(readers[0](), n))


def late_branch(flag: bool) -> None:
    if flag:
        n = int("1000")
    else:
        n = int("2000")

    def read() -> Any:
        return n

    print("branch cell", same(read(), n), same(read(), read()))


shared()
reader = escaped()
kept: Any = reader()
for j in range(200):
    garbage: list[Any] = [int("7654"), float("3.25"), [j]]
print("escaped", same(reader(), kept))
floats()
late_loop()
late_branch(True)
late_branch(False)
