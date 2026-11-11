# mypy idiom (4180 isinstance calls): isinstance(t, (A, B)) narrows a base-typed value to a union of siblings
class Type:
    pass
class Instance(Type):
    def __init__(self, name: str) -> None:
        self.name = name
class TypeVarType(Type):
    def __init__(self, name: str) -> None:
        self.name = name
class NoneType(Type):
    pass
def name_of(t: Type) -> str:
    if isinstance(t, (Instance, TypeVarType)):
        return t.name
    return "<other>"
print(name_of(Instance("int")), name_of(TypeVarType("T")), name_of(NoneType()))
