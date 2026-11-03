# error: enum class Kind is not supported: the compiler makes enum classes from the class statements of a module's body (not of an if or try statement)
# A class statement in an if statement: the loader makes no enum class of it (CPython prints Kind.A)
import sys
from enum import Enum

if sys.version_info >= (3, 11):
    class Kind(Enum):
        A = 1
else:
    class Kind(Enum):
        A = 2


print(Kind.A)
