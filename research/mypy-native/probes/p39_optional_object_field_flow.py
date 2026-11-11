class TypeInfo:
    def __init__(self, name: str) -> None:
        self.name = name
class Instance:
    def __init__(self, info: TypeInfo | None) -> None:
        self.info = info
def f(i: Instance) -> str:
    info = i.info
    if info is None:
        return "?"
    return info.name
def g(i: Instance) -> str:
    if i.info is not None:
        return i.info.name
    return "?"
print(f(Instance(TypeInfo("a"))), f(Instance(None)), g(Instance(TypeInfo("b"))))
