# error: inheritance with generic class templates is not supported
from typing import Iterable


class Variable:
    def __init__(self, value) -> None:
        self.item = value


class Root:
    def __init__(self, values: Iterable[int]) -> None:
        self.value: int = sum(values)


class Child(Root):
    def __init__(self, errors: Variable) -> None:
        self.errors: Variable = errors
        self.value: int = 0


print(Child(Variable(1)).value)
