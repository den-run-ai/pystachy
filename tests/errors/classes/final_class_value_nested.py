# error: final_class_value_nested.py:7: error: a field annotated Final without a type needs a constant value (int, float, str or bool): annotate it Final[T]
from typing import Final


def make() -> list[int]:
    class Local:
        X: Final = [1, 2]

    return Local.X


print(make())
