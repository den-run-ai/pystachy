# Documented deviation (#1513): a star import does not see __all__ that the module binds in a
# top-level try statement, and takes every public name, here also b, which replaces this module's
# own b. CPython takes __all__ = ["a"] and prints "1 main's b".
b = "main's b"
from devmods.alltry import *

print(a, b)
