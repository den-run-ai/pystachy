# error: nt_init.py:4: error: Cannot overwrite NamedTuple attribute __init__
import typing

class Pair(typing.NamedTuple):
    a: int

    def __init__(self, a: int) -> None:
        pass
