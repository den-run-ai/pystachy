# error: cannot infer
from typing import Any


class Box:
    @property
    def value(self) -> Any:
        return self.value


print(Box().value)
