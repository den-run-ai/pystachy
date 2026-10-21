# error: star_rebound_call.py:14: error: 'greet' is bound both by an import and by a def or class, and 'report', which uses it, may run in between (not supported)
# report() calls show(), which reads the greet that import * binds until the def rebinds it.
from emods.star_base import *


def show() -> str:
    return greet("a")


def report() -> str:
    return show()


print(report())


def greet(name: str) -> str:
    return "main " + name
