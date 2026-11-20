# A class inside a function that runs once is a class of the module: its Final attribute is typed by
# its value, as a module's class's is
from typing import Final


def make() -> list[int]:
    class Local:
        X: Final = [1, 2]

    return Local.X


print(make())
