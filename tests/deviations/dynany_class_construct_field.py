# pystachy: dynamic-any
# A class-data __init__ needs descriptor-aware construction. CPython calls None
# and raises TypeError; Pystachy raises an explicit NotImplementedError instead
# of invoking its synthesized empty initializer. Arguments still run first.
from typing import Any


class FieldInitializer:
    __init__: Any = None


def argument() -> int:
    print("argument")
    return 7


# Establish the boxed adapter without trying to construct an impossible seed.
probe: Any = 1
print("layout", isinstance(probe, FieldInitializer))
factory: Any = FieldInitializer
try:
    factory()
    print("constructed")
except (TypeError, NotImplementedError) as exc:
    print(type(exc).__name__ + ":", str(exc))
try:
    factory(argument())
    print("constructed")
except (TypeError, NotImplementedError) as exc:
    print(type(exc).__name__ + ":", str(exc))
