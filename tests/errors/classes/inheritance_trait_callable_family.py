# error: inheritance_trait_callable_family.py:27: error: converting method Primary.f to Callable is not supported where Primary and Trait, bases one object may have, define it apart (their shared base does not)
# A Callable of a bound method is made by an adapter of its method's family, which Primary's f
# and Trait's f, defined apart, do not share: Callables of one object's f read through each would
# not compare equal, as CPython's do.
from collections.abc import Callable


class Root:
    pass


class Primary(Root):
    def f(self) -> int:
        return 1


class Trait(Root):
    def f(self) -> int:
        return 2


class Both(Primary, Trait):
    pass


def via_primary(p: Primary) -> Callable[[], int]:
    return p.f


print(via_primary(Both())())
