# error: @dataclass(...) with arguments is not supported
from dataclasses import dataclass


@dataclass(order=True)
class P:
    x: int
