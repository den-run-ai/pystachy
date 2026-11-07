# pystachy: dynamic-any
# Unselected constructor arms must preserve programs already accepted as registries.
from typing import Any
from registrymods.construct_acceptance import ColdHash, ColdRepr, ImportedDefault


class StringDefault:
    def __init__(self, value: int = "unused") -> None:
        self.value = value


class BoolDefault:
    def __init__(self, value: int = False) -> None:
        self.value = value


class ColdField:
    def __init__(self, value: int) -> None:
        self.value: set[int] = {value}


class WarmField:
    def __init__(self, value: int) -> None:
        self.value = value


class Holder:
    def __init__(self, payload: ColdRepr) -> None:
        self.payload = payload


def zero() -> str:
    return "zero"


def one(value: int) -> int:
    return value + 1


# Bodies and instance layouts are established, but their unused defaults need
# no coercion until a call actually omits the corresponding argument.
string_seed: Any = StringDefault(1)
bool_seed: Any = BoolDefault(2)
imported_seed: Any = ImportedDefault(3)

# Initializers are established, while instance helpers remain unused. Merely
# storing these classes as keys must not compile their lazy repr/hash methods.
repr_seed = ColdRepr(4)
hash_seed = ColdHash(5)

# Holder is already boxed, but its typed parameter's instance is not. Emitting
# an unselected constructor must not introduce that parameter's helper closure.
holder_seed: Any = Holder(repr_seed)
warm_seed: Any = WarmField(6)

registry: dict[Any, Any] = {
    StringDefault: zero,
    BoolDefault: zero,
    ImportedDefault: zero,
    ColdRepr: one,
    ColdHash: one,
    ColdField: one,
    Holder: one,
}
print(registry[StringDefault](), registry[BoolDefault](), registry[ImportedDefault]())
print(string_seed.value, bool_seed.value, imported_seed.value)
print(registry[ColdRepr](10), registry[ColdHash](20), repr_seed.value, hash_seed.value)
print(registry[ColdField](30), warm_seed.value)
print(registry[Holder](40), type(holder_seed) is Holder)
