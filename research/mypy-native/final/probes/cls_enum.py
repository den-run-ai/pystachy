from enum import Enum
from typing import Final
class Color(Enum):
    RED = 1
    GREEN = 2
DEFAULT: Final = Color.RED
class C:
    D: Final = Color.GREEN
print(DEFAULT, C.D)
