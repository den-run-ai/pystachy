# error: must declare method read() (callable fields are not supported)
from typing import Callable


def reader() -> str:
    return "reader"


class A:
    def __init__(self) -> None:
        self.read: Callable[[], str] = reader


class B:
    def read(self) -> str:
        return "b"


def check(value: A | B) -> str:
    return value.read()


print(check(A()))
