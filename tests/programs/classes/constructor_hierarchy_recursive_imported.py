import mods.constructor_hierarchy_recursive_child as models
from mods.constructor_hierarchy_recursive_child import Child as Item


def score(value: models.Base) -> int:
    return value.score()


print(score(models.Base()))
first = Item("51")
second = models.Child(52)
first.next = second
print(score(first), first.next.score(), first.next is second)
second.next = first
print(second.next is first, type(first) is type(second), isinstance(first, models.Base))
