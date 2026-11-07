# pystachy: dynamic-any
# Unselected bodies cannot add unsupported helpers or poison global inference.
from typing import Any
from registrymods.runtime_calls import Hidden, Operand, deferred, poison, stable


def good() -> int:
    return 7


def other(a, b):
    return globals()


def descriptor(a, b):
    return Hidden("{value}")


def dispatch(a, b):
    return a + b


def identity(value: int) -> int:
    return value


# Box the operand without compiling its unsupported arithmetic body. The
# dormant dispatch callback must not activate that body on a later worklist.
held: Any = Operand(3)
functions: list[Any] = [good, other, deferred, descriptor, dispatch, poison]
empty: Any = []
print(functions[0](*empty))
print(functions[1] is other, functions[2] is deferred)
print(identity(stable), type(held) is Operand)
