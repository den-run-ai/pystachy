# A field stored from a field of a parameter whose class the module declares later (a forward
# reference): the later class's fields are inferred first
class Owner:
    def __init__(self, item: "Item") -> None:
        self.item = item
        self.name = item.name
        self.size = item.size * 2


class Item:
    def __init__(self, name: str, size: int) -> None:
        self.name = name
        self.size = size


o = Owner(Item("box", 3))
print(o.name, o.size, o.item.name)
