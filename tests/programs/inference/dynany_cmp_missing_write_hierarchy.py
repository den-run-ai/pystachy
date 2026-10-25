# pystachy: dynamic-any
from typing import Any
class Root:
    pass
class Child(Root):
    def __init__(self) -> None:
        self.items = ['existing']
        self.number = 10
class Grandchild(Child):
    def __init__(self) -> None:
        super().__init__()
        self.last = 11
class Property(Root):
    @property
    def items(self) -> list[str]:
        print('property')
        return ['property']
class Default(Root):
    items = ['default']
class Writer:
    def __init__(self) -> None:
        self.items = [3]
    def __eq__(self, other: 'Writer') -> bool:
        print('body')
        other.items = self.items
        return other.items is self.items
root = Root()
child = Child()
grandchild = Grandchild()
prop = Property()
default = Default()
x: Any = Writer()
y: Any = root
c: Any = child
g: Any = grandchild
p: Any = prop
d: Any = default
print(x == y)
print(root.items)
print(child.items, child.number)
print(grandchild.items, grandchild.number, grandchild.last)
print(prop.items, default.items)
print(vars(child), vars(grandchild))


class NumericWriter:
    def __init__(self) -> None:
        self.number = int('1000')

    def __eq__(self, other: 'NumericWriter') -> bool:
        other.number = self.number
        return other.number == self.number


numeric: Any = NumericWriter()
print(numeric == y)
print(root.number == 1000)
print(child.number, grandchild.number)
print(c.number is c.number, g.number is g.number)
