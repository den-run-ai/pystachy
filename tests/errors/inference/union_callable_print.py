# error: a union that holds a Callable requires narrowing with isinstance() or callable() first
from typing import Callable


def show(v: Callable[[], int] | int) -> None:
    print(v)


show(1)
