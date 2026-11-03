# enum classes of another module: their members, lookups and iteration where it imports them
from dataclasses import dataclass

from enum_palette import Color, Weight


@dataclass
class Item:
    name: str
    color: Color
    weight: Weight


print(Color.RED, Color("g"), Color["RED"].label, Color.default())
print([c.value for c in Color], len(Color), Color.GREEN in Color, "r" in Color)
print(Weight.HEAVY > Weight.LIGHT, Weight.HEAVY + 5, Weight(10), max(Weight))
it = Item("box", Color.GREEN, Weight.HEAVY)
print(it, it.color is Color.GREEN)
counts = {c: 0 for c in Color}
counts[Color.RED] += 2
print(counts, sorted([Weight.HEAVY, Weight.LIGHT]))
