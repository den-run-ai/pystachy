# elif chain of isinstance tests on a base-typed parameter, reading subclass fields
class Type:
    pass
class Instance(Type):
    def __init__(self, name: str) -> None:
        self.name = name
class UnionType(Type):
    def __init__(self, items: list[Type]) -> None:
        self.items = items
def show(t: Type) -> str:
    if isinstance(t, Instance):
        return t.name
    elif isinstance(t, UnionType):
        return " | ".join([show(i) for i in t.items])
    else:
        return "?"
print(show(UnionType([Instance("int"), Instance("str"), Type()])))
