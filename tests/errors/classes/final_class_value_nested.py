# error: final_class_value_nested.py:9: error: a field annotated Final without a type needs a constant value (int, float, str or bool): annotate it Final[T]
# A class inside a function that runs more than once keeps the rejection of a Final value that is
# no constant, which a module's class types by its value
from typing import Final


def make() -> list[int]:
    class Local:
        X: Final = [1, 2]

    return Local.X


print(make())
print(make())
