# error: @property on the special method __match_args__ is not supported
from dataclasses import dataclass


@dataclass
class Point:
    x: int

    @property
    def __match_args__(self) -> tuple[str]:
        raise ValueError("the instance property must not run")


match Point(7):
    case Point(x):
        print("matched", x)
