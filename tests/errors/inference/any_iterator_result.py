# error: iter() returned non-iterator of type 'int'
from typing import Any


class Wrong:
    def __iter__(self) -> Any:
        return 3


print(list(Wrong()))
