# error: expected int, got str
from typing import Any

values: list[Any] = [1]
values.append("text")
