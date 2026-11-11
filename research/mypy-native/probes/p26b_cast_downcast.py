from typing import cast
class Type:
    pass
class Instance(Type):
    def __init__(self, name: str) -> None:
        self.name = name
def g(t: Type) -> str:
    return cast(Instance, t).name
print(g(Instance("b")))
