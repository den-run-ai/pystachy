from typing import Iterable


class Total:
    def __init__(self, values: Iterable[int]) -> None:
        self.total: int = sum(values)

    def score(self) -> int:
        return self.total


class Inherited(Total):
    pass


class Bonus(Total):
    def __init__(self, values: Iterable[int], bonus=5) -> None:
        super().__init__(values)
        self.bonus: int = int(bonus)

    def score(self) -> int:
        return self.total + self.bonus


class Invalid(Total):
    def score(self) -> int:
        return self.missing


class InvalidChild(Invalid):
    pass


def unused(value: Invalid) -> int:
    return value.score()
