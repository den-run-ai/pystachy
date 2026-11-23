# What a template hierarchy's classes inherit and override besides methods: class attributes,
# properties with setters, special methods that operators, str() and containers call, and
# generators (#962).
class Item:
    kind = "item"
    count = 0

    def __init__(self, name, weight):
        self.name = name
        self._weight = weight

    @property
    def weight(self):
        return self._weight

    @weight.setter
    def weight(self, w) -> None:
        self._weight = w

    def __str__(self) -> str:
        return self.kind + ":" + self.name

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Item) and self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)

    def parts(self):
        yield self.name
        yield self.kind


class Box(Item):
    kind = "box"


class Crate(Item):
    kind = "crate"

    def __init__(self, name: str) -> None:
        super().__init__(name, 100)

    def __str__(self) -> str:
        return "crate<" + super().__str__() + ">"

    def parts(self):
        yield "lid"
        yield from super().parts()


items = [Item("a", 3), Box("b", 1), Crate("c"), Box("a", 9)]
for x in items:
    print(str(x), x.kind, x.weight, list(x.parts()))
items[1].weight = 50
print(items[1].weight, items[1] == items[3], items[0] == items[3], Box("a", 0) in items, items.index(Box("c", 7)))
print(sorted(items, key=lambda z: z.weight)[0].name, max(items, key=lambda z: z.weight).name)
print(len({x for x in items}), Item.kind, Box.kind, Crate.kind, Box.count)
print(f"{items[2]}", [str(y) for y in sorted(items, key=lambda z: z.name)])
