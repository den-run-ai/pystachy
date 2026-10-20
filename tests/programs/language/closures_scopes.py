# A def inside a function is a scope of its own: what it assigns, and its global statements, do
# not make names of the function around it local or global (and a dead branch's def neither)
import sys

y = 5


def outer() -> int:
    def inner() -> int:
        y = 1
        return y
    return y + inner()


x = 0


def outer2() -> int:
    x = 1

    def inner2() -> None:
        global x
        x = 2
    inner2()
    return x


z = 0


def outer3() -> int:
    def setz() -> None:
        global z
        z = 7
    setz()
    return z


w = 0


def outer4() -> int:
    w = 1
    if sys.platform == "win32-never":
        def inner4() -> None:
            global w
            w = 5
    return w


print(outer(), outer2(), x, outer3(), z, outer4(), w)
