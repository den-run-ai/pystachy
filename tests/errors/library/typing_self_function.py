# error: typing.Self is only supported in a class, for its methods and fields
from typing import Self


def f(x: Self) -> None:
    pass
