class Type:
    pass
class Instance(Type):
    def __init__(self, name: str) -> None:
        self.name = name
def f(t: Type | None) -> str:
    assert t is not None
    assert isinstance(t, Instance)
    return t.name
print(f(Instance("a")))
