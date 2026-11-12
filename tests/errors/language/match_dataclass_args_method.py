# error: class patterns require a dataclass without a hierarchy, attribute hooks or custom __match_args__
from dataclasses import dataclass


@dataclass
class Point:
    x: int

    def __match_args__(self) -> tuple[str]:
        return ("x",)


match Point(7):
    case Point(x):
        print("matched", x)
