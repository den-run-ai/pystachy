# error: lib_functools_cached_property_enum.py:11: error: enum class Color's body is not supported: an enum class has members (NAME = value), methods and a docstring
from enum import Enum
from functools import cached_property


class Color(Enum):
    RED = 1
    BLUE = 2

    @cached_property
    def label(self) -> str:
        return self.name.lower()


print(Color.RED.label)
