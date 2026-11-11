# string/forward TypeAlias used across the module (26 TypeAlias imports)
from typing import TypeAlias
class Type:
    def __init__(self, n: str) -> None:
        self.n = n
TypeOrNone: TypeAlias = "Type | None"
Triple: TypeAlias = tuple[str, int, "Type | None"]
def f(x: TypeOrNone) -> str:
    return "none" if x is None else x.n
t: Triple = ("a", 1, Type("z"))
print(f(None), f(t[2]))
