# A global that the program's module-level code only ever assigns None (also as x: Final =
# None) reads as None, in module code and in functions, as a local does.
from typing import Final

x = None
LAST: Final = None


def show(tag: str) -> None:
    print(tag, x, LAST, x is None, LAST is not None)


show("f")
print(x, x == None, LAST is None, f"{x}!", str(LAST), repr(x))
x = None
show("g")
