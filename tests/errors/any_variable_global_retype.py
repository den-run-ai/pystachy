# error: expected int, got str
from typing import Any

value: Any = 1
value = "text"
print(value)
