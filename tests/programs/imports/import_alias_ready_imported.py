from typing import Callable
from mods.alias_base import inc
import mods.alias_mid


def call() -> int:
    return plus(6)


def shadow(plus: Callable[[int], int]) -> int:
    return plus(8)


def conditional(flag: bool) -> int:
    if flag:
        from mods.alias_mid import plus_one as plus
    return plus(9)


deferred = lambda: plus(40)
print("shadow", shadow(inc))
try:
    print(conditional(False))
except UnboundLocalError as e:
    print("UnboundLocalError", e)
print("conditional", conditional(True))
try:
    print(call())
except NameError as e:
    print("NameError", e)
try:
    print(deferred())
except NameError as e:
    print("NameError", e)
plus = inc
print(call(), deferred())
