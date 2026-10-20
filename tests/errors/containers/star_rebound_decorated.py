# error: star_rebound_decorated.py:10: error: 'greet' is bound both by an import and by a def or class, and a decorator here may run a function or class that uses it in between (not supported)
# keep() may call show(), or keep it for code before the def that rebinds greet.
from emods.star_base import *


def keep(f):
    return f


@keep
def show() -> str:
    return greet("a")


def greet(name: str) -> str:
    return "main " + name


print(show())
