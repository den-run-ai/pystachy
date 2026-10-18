import devmods.star_rebound_self as myself
from devmods.star_rebound_base import greet

try:
    print(myself.greet())
except NameError as e:
    print(type(e).__name__, e)


def greet() -> str:
    return "rebound"
