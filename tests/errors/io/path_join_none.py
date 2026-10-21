# error: argument 2 of os.path.join() may be None (str | None); test it
import os


def f(s: str | None) -> str:
    return os.path.join("a", s)


print(f("b"))
