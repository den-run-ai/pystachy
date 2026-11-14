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


def score(value: Total) -> int:
    return value.score()


def items():
    yield 6
    yield 7


objects: list[Total] = [Total([1, 2]), Inherited((3, 4)), Bonus(items(), "8")]
for obj in objects:
    print(score(obj), isinstance(obj, Total), type(obj).__name__)
print(type(Bonus([1])) is type(Bonus((2, 3))))
