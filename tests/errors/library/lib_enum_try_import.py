# error: enum class Color is not supported: the compiler makes enum classes from the class statements of a module's body (not of an if or try statement) whose base the body's import statements name
# Enum imported in a try statement: the loader makes no enum class of Color (CPython prints <Color.RED: 1>)
try:
    from enum import Enum
except ImportError:
    Enum = object


class Color(Enum):
    RED = 1


print(repr(Color.RED))
