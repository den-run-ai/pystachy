# pystachy: dynamic-any
# A runtime call must not require unusable defaults or dormant typed adapters.
from typing import Any
from registrymods.construct_acceptance import ColdRepr


class ColdDefault:
    def __init__(self, value: int = "unused") -> None:
        self.value = value


def cold_default(value: int = "unused") -> int:
    return value


def native_parameter(values: list[str]) -> int:
    return len(values)


def nominal_parameter(value: ColdRepr) -> int:
    return value.value


def identity(value: int) -> int:
    return value


seed: Any = ColdDefault(1)
factory: Any = ColdDefault
unboxed = ColdRepr(2)
handlers: list[Any] = [cold_default, native_parameter, nominal_parameter]
function: Any = identity
args: Any = [7]
print(function(*args), seed.value, unboxed.value)
print(handlers[0](*args), handlers[1] is native_parameter, handlers[2] is nominal_parameter)
restored = factory(*args)
print(type(restored) is ColdDefault, restored.value)
