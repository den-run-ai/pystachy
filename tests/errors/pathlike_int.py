# error: os.PathLike is only supported in a union with str, not with int
from os import PathLike
from typing import Union


def f(p: Union[int, PathLike[str], None]) -> None:
    print(p)
