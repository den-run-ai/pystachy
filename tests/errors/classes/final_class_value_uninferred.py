# error: final_class_value_uninferred.py:6: error: cannot infer the type of class attribute 'KEYS'; annotate it (KEYS: Final[T] = ...)
from typing import Final


class Table:
    KEYS: Final = {1, 2}


print(Table.KEYS)
