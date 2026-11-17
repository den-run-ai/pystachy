# Documented deviation (#1513): a star import does not see __all__ that the module binds in an if
# statement's branch, and takes every public name, here also b. CPython runs the branch, takes
# __all__ = ["a"] and prints "5 main's b".
b = "main's b"
from devmods.allif import *

print(a, b)
