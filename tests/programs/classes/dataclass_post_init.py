# The __init__ that @dataclass generates calls __post_init__ last, when the class defines it:
# fields computed from the others, and validation that raises.
from dataclasses import dataclass


@dataclass
class P:
    raw: str
    n: int = 0

    def __post_init__(self) -> None:
        self.n = len(self.raw)


@dataclass
class DC:
    x: int

    def __post_init__(self) -> None:
        if self.x < 0:
            raise ValueError("negative")


@dataclass
class Own:
    a: int

    def __init__(self, a: int) -> None:
        self.a = a * 2

    def __post_init__(self) -> None:
        self.a = -1


print(P("abc"), P("de", 9))
try:
    DC(-1)
    print("constructed")
except ValueError as e:
    print("caught", e)
print(DC(3), Own(4))
DC(-2)
