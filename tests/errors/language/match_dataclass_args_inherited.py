# error: class patterns require a dataclass without a hierarchy, attribute hooks or custom __match_args__
from dataclasses import dataclass


@dataclass
class Parent:
    x: int

    def __match_args__(self) -> tuple[str]:
        return ("x",)


@dataclass(match_args=False)
class Child(Parent):
    pass


match Child(7):
    case Child(x):
        print("matched", x)
