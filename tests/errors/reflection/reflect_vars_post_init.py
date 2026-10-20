# error: reflect_vars_post_init.py:14: error: vars() of D is not supported: it assigns attribute extra, which is no field of its class (#486)
from dataclasses import dataclass


@dataclass
class D:
    x: int

    def __post_init__(self) -> None:
        self.extra = self.x * 2


# (a compile-time error, not a crash of the compiler)
print(vars(D(1)))
