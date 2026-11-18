# error: classvar_dataclass.py:9: error: typing.ClassVar (a class attribute) is not supported
# (a dataclass leaves a ClassVar out of its fields, which this compiler does not model)
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class Config:
    count: ClassVar[int] = 0
    name: str = "x"


print(Config())
