# A module that does not opt in to dynamic Any, storing values as object
# (tests/programs/classes/object_storage_from_dynamic.py imports it)
class Item:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"Item({self.name!r})"


STORE: list[object] = [1, "two", None, Item("x")]


def get(i: int) -> object:
    return STORE[i]


def put(v: object) -> None:
    STORE.append(v)


def kind(v: object) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int " + str(v + 1)
    if isinstance(v, Item):
        return "Item " + v.name
    return "other " + repr(v)
