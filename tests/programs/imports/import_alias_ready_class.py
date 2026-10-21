from mods.alias_base import Box


def argument() -> int:
    print("class argument")
    return 7


def make() -> int:
    return Crate(argument()).v


def check(value: Box) -> bool:
    return isinstance(value, Crate)


def describe() -> str:
    return Crate.__name__


value = Box(1)
try:
    print(make())
except NameError as e:
    print("NameError", e)
try:
    print(check(value))
except NameError as e:
    print("NameError", e)
try:
    print(describe())
except NameError as e:
    print("NameError", e)
Crate = Box
print(make(), check(value), describe())
