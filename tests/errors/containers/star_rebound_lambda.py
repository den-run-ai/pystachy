# error: star_rebound_lambda.py:4: error: 'greet' is bound both by an import and by a def or class, and a lambda or generator expression here that reads it may run in between (not supported)
# The lambda, made before the import and kept, runs in between: CPython's call reads the greet that
# import * binds, until the def rebinds it.
handlers = [lambda: greet("a")]
from emods.star_base import *

print(handlers[0]())


def greet(name: str) -> str:
    return "main " + name
