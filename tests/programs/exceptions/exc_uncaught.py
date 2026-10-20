# an exception nothing catches: the finally blocks on its way run first, and the program ends
# with CPython's last traceback line and status 1


def inner(xs: list[int]) -> int:
    try:
        return xs[5]
    finally:
        print("inner finally")


def outer() -> None:
    try:
        print(inner([1, 2]))
    except KeyError:
        print("not this one")
    finally:
        print("outer finally")


try:
    outer()
finally:
    print("module finally")
