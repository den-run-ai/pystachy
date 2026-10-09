# error: @dataclass(order=...) is not supported: of its arguments, only kw_only= is
from dataclasses import dataclass


@dataclass(order=True)
class P:
    x: int
