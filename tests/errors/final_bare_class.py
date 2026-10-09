# error: final_bare_class.py:6: error: Final without a type is only supported where a value gives it (x: Final = v, outside class bodies); write Final[T]
from typing import Final


class Limits:
    top: Final = 10


print(Limits().top)
