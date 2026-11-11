from typing import NamedTuple
class Key(NamedTuple):
    name: str
    line: int
k = Key("x", 3)
print(k.name, k[1])
