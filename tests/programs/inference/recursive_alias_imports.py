"""A qualified alias keeps one named graph across imports and ordinary aliases."""
from mods.recursive_values import Tree, make
import mods.recursive_values as values

type Alias = Tree


def identity(value: values.Tree) -> Alias:
    return value


def make_items() -> list[Tree]:
    return [make(), "end"]


value: Alias = identity(make())
items: list[Tree] = make_items()
print(value, items, value == items[0])

