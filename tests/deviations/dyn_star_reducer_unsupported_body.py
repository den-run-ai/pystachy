# pystachy: dynamic-any
# Selecting an unavailable generic body fails explicitly after argument effects.
from typing import Any


def unsupported(a, b):
    globals()
    return a + b


def arguments() -> Any:
    print("arguments")
    return [4, 5]


function: Any = unsupported
try:
    print(function(*arguments()))
except NotImplementedError as error:
    print(str(error))
