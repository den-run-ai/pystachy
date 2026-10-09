# error: an exception class with a decorator (@dataclass) is not supported
from dataclasses import dataclass


@dataclass
class Problem(Exception):
    code: int


raise Problem(3)
