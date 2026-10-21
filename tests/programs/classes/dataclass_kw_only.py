# @dataclass(kw_only=True) makes its __init__ take every field by keyword only, in any order of
# defaults; kw_only=False is the default
from dataclasses import dataclass


@dataclass(kw_only=True)
class D:
    a: int
    b: int = 2
    c: str

    @classmethod
    def mk(cls) -> "D":
        return cls(a=1, c="x")


@dataclass(kw_only=False)
class E:
    x: int


print(D.mk(), D(c="y", b=3, a=0), D(a=1, c="z") == D(c="z", a=1), E(5))
