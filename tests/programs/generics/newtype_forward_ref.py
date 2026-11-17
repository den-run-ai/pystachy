# A string in a NewType's type is a forward reference, which CPython does not evaluate where the
# assignment runs: the name in it may be bound later, here by the import below
from typing import NewType

Shapes = NewType("Shapes", list["Circle"])
from mods.shapes import Circle

print(len(Shapes([Circle(1.0), Circle(2.0)])))
