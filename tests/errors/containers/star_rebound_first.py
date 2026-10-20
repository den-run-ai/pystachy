# error: star_rebound_first.py:8: error: 'greet' is bound both by an import and by a def or class (not supported)
# The import rebinds the def's name: an import after the def or class is no rebinding of it.
def greet(name: str) -> str:
    return "main " + name


print(greet("a"))
from emods.star_base import *

print(greet("b"))
