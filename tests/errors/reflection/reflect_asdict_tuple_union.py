# error: reflect_asdict_tuple_union.py:13: error: asdict() of Item: str and tuple[int,int] have no common type
# asdict()'s values of different types join in a union, which cannot hold a tuple
from dataclasses import asdict, dataclass


@dataclass
class Item:
    name: str
    pair: tuple[int, int]
    ok: bool


print(asdict(Item("a", (1, 2), True)))
