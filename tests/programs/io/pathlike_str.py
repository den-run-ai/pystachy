# os.PathLike in a union with str is dropped: str is the only path type a program can have,
# so str | os.PathLike[str] is a str, and os.fspath() of a str returns it
import os
from dataclasses import dataclass
from os import PathLike
from typing import Optional, Union


def read_name(path: str | os.PathLike[str]) -> str:
    return os.fspath(path)


def maybe(path: "os.PathLike[str] | str | None" = None) -> str:
    return "none" if path is None else os.fspath(path)


def u(p: Union[str, PathLike[str]], q: Optional[Union[str, os.PathLike]] = None) -> str:
    return p + ("" if q is None else q)


class Config:
    def __init__(self, path: str | os.PathLike[str], data: str | None = None) -> None:
        self.path = os.fspath(path)
        self.data = data


@dataclass
class Entry:
    path: str | os.PathLike[str]
    alt: str | None | os.PathLike[str] = None


print(read_name("a/b.ini"), maybe(), maybe("x"), u("p"), u("p", "q"))
c = Config("setup.cfg")
print(c.path, c.data, c.path.upper())
e = Entry("e.ini")
print(e, Entry("x", "y") == Entry("x", "y"), os.fspath(e.path) is e.path)
names: list[str | os.PathLike[str]] = ["a", "b"]
print(names, [os.fspath(n) for n in names])
o = os.getenv("PYSTACHY_NO_SUCH_VAR")
print(os.fspath(o if o is not None else "default"))
print(os.fspath(o))
