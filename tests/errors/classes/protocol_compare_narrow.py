# error: expected Money, got Token (making the table of Token as Named (for Money == its object)
# Any two implementations may meet when values of the protocol are compared. CPython calls
# Money.__eq__ with a Token whatever its annotation says, which a method annotated to take only a
# Money cannot be compiled for: annotate other as object and test it with isinstance()
from typing import Protocol


class Named(Protocol):
    def name(self) -> str: ...


class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents

    def name(self) -> str:
        return "money"

    def __eq__(self, other: "Money") -> bool:
        return self.cents == other.cents


class Token:
    def name(self) -> str:
        return "token"


xs: list[Named] = [Money(1), Token()]
print(xs[0] == xs[0])
