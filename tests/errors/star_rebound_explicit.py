# error: star_rebound_explicit.py:5: error: 'greet' is bound both by an import and by a def or class, and is read here in between (not supported)
# As locale keeps _localeconv = localeconv before its def localeconv(), which calls it.
from emods.star_base import greet

_greet = greet


def greet(name: str) -> str:
    return "main " + _greet(name)


print(greet("a"))
