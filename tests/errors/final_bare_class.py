# error: final_bare_class.py:6: error: a bare Final needs a value to give its type (x: Final = v), outside class bodies; write Final[T]
from typing import Final


class Limits:
    top: Final = 10


print(Limits().top)
