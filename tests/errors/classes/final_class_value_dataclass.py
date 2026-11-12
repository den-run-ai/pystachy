# error: final_class_value_dataclass.py:9: error: a field annotated Final without a type needs a constant value (int, float, str or bool): annotate it Final[T]
# (a dataclass field, whose default dataclass checks: a class attribute's inference does not apply)
from dataclasses import dataclass
from typing import Final


@dataclass
class Config:
    paths: Final = ("a", "b")


print(Config())
