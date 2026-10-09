# error: os.PathLike is only supported in a union with str (str | os.PathLike[str] is a str: Pystachy has no other path type)
import os


def f(p: os.PathLike[str]) -> None:
    print(p)
