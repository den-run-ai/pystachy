# A class whose __init__ calls a generic class's constructor becomes a class template, also where
# the field is annotated with a named specialization: it can then not be a base class.
from types import MappingProxyType

class Sig:
    def __init__(self, names: list[str]) -> None:
        params: dict[str, int] = {}
        for i, n in enumerate(names):
            params[n] = i
        self._parameters: MappingProxyType[str, int] = MappingProxyType(params)

class Sub(Sig):
    pass

print(len(Sub(["a", "b"])._parameters))
