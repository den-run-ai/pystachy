# error: unsupported type annotation
from typing import Annotated

value: Annotated[int, "Any"] = "not an int"
print(value)
