# error: any_field.py:9: error: typing.Any is only supported in the parameter and return annotations of a function
# A field annotated Any is storage, which no call types
from dataclasses import dataclass
from typing import Any


@dataclass
class Item:
    value: Any


print(Item(1))
