# error: star_rebound_genexp.py:4: error: 'greet' is bound both by an import and by a def or class, and a lambda or generator expression here that reads it may run in between (not supported)
# The generator expression, made before the import, calls greet as next() iterates it, in
# between: CPython's reads the greet that import * binds, until the def rebinds it.
names = (greet(n) for n in ["a", "b"])
from emods.star_base import *

print(next(names))


def greet(name: str) -> str:
    return "main " + name
